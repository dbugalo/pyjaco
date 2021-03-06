import ist
import sys
G = globals()
for x in ist.__all__:
    G["I%s" % x] = getattr(ist, x)
import istcompiler
import isttransform

class Transformer(isttransform.Transformer):

    ops_binop = {
        "Add": "add",
        "Sub": "sub",
        "Div": "div",
        "Mod": "mod",
        "Pow": "pow",
        "Mult": "mul",
        "BitOr": "bitor",
        "BitAnd": "bitand",
        "BitXor": "bitxor",
        "LShift": "lshift",
        "RShift": "rshift",
        "FloorDiv": "floordiv",
    }

    ops_augassign = {
        "Add"     : "iadd",
        "Sub"     : "isub",
        "Div"     : "idiv",
        "Mult"    : "imul",
        "LShift"  : "ilshift",
        "RShift"  : "irshift",
        "BitOr"   : "ibitor",
        "BitAnd"  : "ibitand",
        "BitXor"  : "ibitxor",
        "FloorDiv": "ifloordiv",
        "Pow"     : "ipow",
    }

    ops_compare = {
        "Eq": "eq",
        "NotEq": "ne",
        "Gt": "gt",
        "Lt": "lt",
        "GtE": "ge",
        "LtE": "le",
    }

    uopmap = dict(
        UAdd = "pos",
        USub = "neg",
        Invert = "invert",
        )

    name_map = {
        'super' : '$super',
        'delete': '$delete',
        'default': '$default',
    }

    def compute(self, tree):
        self.index_var = 0
        self.future_division = False
        self.scope = []
        self.exceptions = []
        self._loops = []
        self._class_name = []
        self.emulate_generators = True
        return self.comp(tree)

    def alloc_var(self):
        self.index_var += 1
        return "$v%d" % self.index_var

    def ispure(self, tree):
        return isinstance(tree, IName)

    def purecall(self, obj, func, *args):
        target = self.comp(obj)
        args = [self.comp(n) for n in args]
        if self.ispure(obj):
            return ICall(
                func = IGetAttr(base = target, attr = func),
                args = [target] + args,
                keywords = [],
                kwargs = None,
                varargs = None)
        else:
            return ICall(func = IName(id = "$PY.call"), args = [target, IString(value = func)] + args)

    def node_name(self, node):
        if node.id in ["copyright", "credits", "license", "help"] + ["abs", "all", "any", "apply", "bin", "callable", "chr", "cmp", "coerce", "delattr", "dir", "enumerate", "filter", "getattr", "hasattr", "hash", "hex", "id", "intern", "isinstance", "issubclass", "len", "map", "max", "min", "oct", "ord", "pow", "quit", "range", "reduce", "repr", "reversed", "round", "setattr", "sorted", "staticmethod", "sum", "type", "unichr", "xrange", "zip"] + ["Exception", "TypeError", "IOError", "ValueError", "ZeroDivisionError", "StopIteration", "IndexError"]:
            return ist.GetAttr(base = ist.Name(id = "__builtins__"), attr = "PY$%s" % node.id)
        else:
            node.id = self.name_map.get(node.id, node.id)
            return node

    def node_getattr(self, node):
        if isinstance(node.base, ist.Name) and node.base.id == "__builtins__":
            return node
        else:
            return ist.Call(func = ist.GetAttr(base = IName(id = "$PY"), attr = "getattr"), args = [self.comp(node.base), ist.String(value = node.attr)], keywords = [], kwargs = None, varargs = None)

    def node_tuple(self, node):
        return ist.Call(func = ist.Name(id = "tuple"), args = [ist.List(values = self.comp(node.values))])

    def node_return(self, node):
        if not node.expr:
            node.expr = [ist.Name(id = "None")]
        else:
            node.expr = self.comp(node.expr)
        return node

    def node_dict(self, node):
        els = []
        for k, v in zip(node.keys, node.values):
            els.append(self.comp(k))
            els.append(self.comp(v))
        return ist.Call(func = ist.Name(id = "dict"), args = [ist.List(values = els)])

    def node_list(self, node):
        return ist.Call(func = ist.Name(id = "list"), args = [ist.List(values = self.comp(node.values))])

    def node_getitem(self, node):
        target = self.comp(node.value)
        func = "PY$__getitem__"
        return self.purecall(node.value, func, node.slice)

    def node_number(self, node):
        if isinstance(node.value, (int, long)):
            if 0 <= node.value <= 9:
                return ist.Name(id = "$c%s" % node.value)
            elif -2**53 <= node.value <= 2**53:
                return ist.Call(func = ist.Name(id = "int"), args = [node])
            else:
                raise NotImplementedError("JS doesn't support long numbers")
        elif isinstance(node.value, float):
            return ist.Call(func = ist.Name(id = "float"), args = [node])
        else:
            raise NotImplementedError("Unknown numeric type: %s" % node.n.__class__.__name__)

    def node_slice(self, node):
        lower = self.comp(node.lower) if node.lower else IName(id = "None")
        upper = self.comp(node.upper) if node.upper else IName(id = "None")
        step  = self.comp(node.step)  if node.step  else IName(id = "None")
        return ist.Call(func = ist.Name(id = "slice"), args = [lower, upper, step])

    def node_string(self, node):
        return ist.Call(func = ist.Name(id = "str"), args = [ist.String(value = node.value)])

    def node_call(self, node):
        js = []

        posargs = self.comp(node.args)

        if isinstance(node.func, ist.GetAttr) and isinstance(node.func.base, IName) and node.func.base.id == '__builtins__' and node.func.attr == "print":
            node.func.attr = "PY$print"

        cooked = IDict(keys = [], values = [])

        if node.varargs:
            cooked.keys.append(IString(value = "varargs"))
            cooked.values.append(self.comp(node.varargs))

        if node.keywords:
            kws = IDict(keys = [], values = [])
            for key, value in node.keywords:
                kws.keys.append(IString(value = self.name_map.get(key, key)))
                kws.values.append(self.comp(value))
            cooked.keys.append(IString(value = "kw"))
            cooked.values.append(kws)

        if node.kwargs:
            cooked.keys.append(IString(value = "kwargs"))
            cooked.values.append(self.comp(node.kwargs))

        if cooked.keys:
            if not node.varargs:
                cooked.keys.append(IString(value = "varargs"))
                cooked.values.append(IList(values = []))
            cooked = [cooked]
        else:
            cooked = []

        return ICall(func = self.comp(node.func), args = posargs + cooked)

    def node_binop(self, node):
        if node.op == "Div":
            if self.future_division:
                op = "div"
            else:
                op = "floordiv"
        else:
            op = self.ops_binop[node.op]
        func = "PY$__%s__" % op
        return self.purecall(node.left, func, node.right)

    def node_unaryop(self, node):
        if node.op == "Not":
            return ist.Call(func = ist.GetAttr(base = ist.Name(id = "$PY"), attr = "__not__"), args = [self.comp(node.lvalue)])
        elif node.op in self.uopmap:
            func = "PY$__%s__" % self.uopmap[node.op]
            return self.purecall(node.lvalue, func)
        else:
            raise NotImplementedError()

    def node_if(self, node):
        node.cond = ist.Compare(lvalue = ist.Call(func = ist.Name(id = "bool"), args = [self.comp(node.cond)]), ops = ["Eq"], comps = [ist.Name(id = "True")])
        node.body = self.comp(node.body)
        if node.orelse:
            node.orelse = self.comp(node.orelse)
        return node

    def node_while(self, node):
        if node.orelse:
            orelse_var = self.alloc_var()
            self._loops.append(orelse_var)
            decl = IVar(name = orelse_var, expr = ist.Name(id = "true"))

        node.cond = ist.Compare(lvalue = ist.Call(func = ist.Name(id = "bool"), args = [self.comp(node.cond)]), ops = ["Eq"], comps = [ist.Name(id = "True")])
        node.body = self.comp(node.body)

        if node.orelse:
            self._loops.pop()
            code = [decl, node, IIf(cond = IName(id = orelse_var), body = self.comp(node.orelse))]
            node.orelse = None
            return code
        else:
            return node

    def node_break(self, node):
        if self._loops:
            return [IAssign(lvalue = [IName(id = self._loops[-1])], rvalue = IName(id = "false")), node]
        else:
            return node

    def node_foreach(self, node):
        if isinstance(node.target, ist.Name):
            for_target = self.comp(node.target)
        elif isinstance(node.target, ist.Tuple):
            for_target = ist.Name(id = self.alloc_var())
        else:
            raise JSError("Advanced for-loop decomposition not supported")

        js = []

        for_iter = self.comp(node.iter)
        iter_var = self.alloc_var()
        exc_var = self.alloc_var()

        if node.orelse:
            orelse_var = self.alloc_var()
            self._loops.append(orelse_var)
            js.append(ist.Var(name = orelse_var, expr = ist.Name(id = "true")))

        js.append(ist.Var(name = for_target.id))
        js.append(ist.For(body = self.comp(node.body),
                          init = ist.Var(name = iter_var, expr = ist.Call(func = ist.Name(id = "iter"), args = [for_iter])),
                          cond = ist.Assign(lvalue = [for_target], rvalue = ist.Call(func = ist.GetAttr(base = ist.Name(id = "$PY"), attr = "next"), args = [ist.Name(id = iter_var)])),
                          incr = None
                          ))

        if isinstance(node.target, ITuple):
            decom = []
            for i, x in enumerate(node.target.values):
                decom.append(IVar(name = x.id, expr = ICall(func = (IGetAttr(base = for_target, attr = "PY$__getitem__")), args = [for_target, INumber(value = i)])))
            js[-1].body = decom + js[-1].body

        if node.orelse:
            js.append(IIf(cond = IName(id = orelse_var), body = self.comp(node.orelse)))
            self._loops.pop()

        return js

    def node_compare(self, node):
        assert len(node.ops) == len(node.comps)
        if len(node.ops) == 1:
            return self.compare_simple(node.lvalue, node.ops[0], node.comps[0])
        else:
            var = self.alloc_var()
            body = []
            body.append(IVar(name = var, expr = self.comp(node.lvalue)))

            complambda = ILambda(body = body, params = None)

            lastif = complambda
            lastvar = var
            for i, op, val in zip(range(len(node.ops)), node.ops, node.comps):
                newvar = self.alloc_var()
                lastif.body.append(IAssign(lvalue = [IName(id = newvar)], rvalue = self.comp(val)))
                I = IIf(cond = ICompare(lvalue = ICall(func = IName(id = "bool"), args = [self.compare_simple(IName(id = lastvar), op, IName(id = newvar))]), ops = ["Eq"], comps = [IName(id = "True")]), body = [])
                lastif.body.append(I)
                lastif = I
                lastvar = newvar

            lastif.body.append(IReturn(expr = IName(id = "True")))

            body.append(IReturn(expr = IName(id = "False")))
            return ICall(func = complambda, args = [])

    def compare_simple(self, lvalue, op, rvalue):
        if op in self.ops_compare:
            func = "PY$__%s__" % self.ops_compare[op]
            return self.purecall(lvalue, func, rvalue)
        elif op == "In":
            func = "PY$__contains__"
            return self.purecall(rvalue, func, lvalue)
        elif op == "Is":
            return ist.Call(func = ist.GetAttr(base = ist.Name(id = "$PY"), attr = "__is__"), args = [self.comp(lvalue), self.comp(rvalue)])
        elif op == "NotIn":
            return ist.Call(func = ist.GetAttr(base = ist.Name(id = "$PY"), attr = "__not__"), args = [self.compare_simple(lvalue, "In", rvalue)])
        else:
            raise NotImplementedError(op)

    def node_importfrom(self, node):
        if node.module == "__future__" and node.names == dict(division = None):
            self.future_division = True
            return None
        else:
            raise NotImplementedError()

    def node_assign(self, node):
        res = []
        if len(node.lvalue) > 1:
            tmp = self.alloc_var()
            res.append(ist.Var(name = tmp, expr = self.comp(node.rvalue)))
            for lval in node.lvalue:
                res.extend(self.assign_simple(lval, ist.Name(id = tmp)))
            return res
        else:
            return self.assign_simple(node.lvalue[0], self.comp(node.rvalue))

    def assign_simple(self, target, value):
        if isinstance(target, (ist.Tuple, ist.List)):
            t1 = self.alloc_var()
            js = [ist.Var(name = t1, expr = value)]

            for i, target in enumerate(target.values):
                var = target.id
                assert isinstance(target, IName)
                expr = ICall(func = IGetAttr(base = IName(id = t1), attr = "PY$__getitem__"), args = [IName(id = t1), INumber(value = i)])
                if isinstance(target, IName) and not (var in self.scope):
                    self.scope.append(var)
                    js.append(IVar(name = target.id, expr = expr))
                else:
                    js.append(IAssign(lvalue = [target], rvalue = expr))
        elif isinstance(target, ist.GetItem):
            if isinstance(target.slice, ist.Slice):
                func = "PY$__setslice__"
                slice = target.slice
                lower = self.comp(slice.lower) if slice.lower else IName(id = "None")
                upper = self.comp(slice.upper) if slice.upper else IName(id = "None")
                step  = self.comp(slice.step ) if slice.step  else IName(id = "None")
                js = [self.purecall(target.value, func, lower, upper, step, value)]
            else:
                js = [ist.Call(func = ist.GetAttr(base = self.comp(target.value), attr = "PY$__setitem__"), args = [self.comp(target.value), self.comp(target.slice), value])]
        elif isinstance(target, ist.Name):
            var = target.id
            if var in self.scope:
                js = [IAssign(lvalue = [IName(id = var)], rvalue = value)]
            else:
                self.scope.append(var)
                js = [ist.Var(name = var, expr = value)]
        elif isinstance(target, ist.GetAttr):
            js = [ist.Call(func = ist.GetAttr(base = IName(id = "$PY"), attr = "setattr"), args = [self.comp(target.base), IString(value = target.attr), value])]
        else:
            raise NotImplementedError("Unsupported assignment type", target)
        return js

    def node_function(self, node):
        defaults = [None] * (len(node.params.args) - len(node.params.defaults)) + node.params.defaults

        js = []

        self.scope = [arg for arg in node.params.args]

        pyargs = IName(id = "$pyargs")
        pyargs_kw = IGetAttr(base = pyargs, attr = "kw")

        newargs = self.alloc_var()

        js.append(IVar(name = pyargs.id,  expr = ICall(func = IName(id = "__uncook"),  args = [IName(id = "arguments")])))
        js.append(IVar(name = newargs, expr = IGetAttr(base = IName(id = "$pyargs"), attr = "varargs")))

        if node.params.kwargs:
            js.append(IVar(name = node.params.kwargs, expr = ICall(func = IName(id = "dict"), args = [IGetAttr(base = pyargs, attr = "kwargs")])))

        if node.params.varargs:
            js.append(IVar(name = node.params.varargs, expr = IName(id = "tuple(%s.slice(%s))" % (newargs, len(node.params.args)))))

        for i, arg in enumerate(node.params.args):
            arg = self.name_map.get(arg, arg)
            if defaults[i] == None:
                js.append(
                    IVar(
                        name = arg,
                        expr = IBinOp(left = IGetAttr(base = pyargs_kw, attr = arg), op = "Or", right = IGetItem(value = IName(id = newargs), slice = INumber(value = i)))))
            else:
                js.append(IVar(name = arg, expr = IGetItem(value = IName(id = newargs), slice = INumber(value = i))))
                js.append(IIf(cond = ICompare(lvalue = IName(id = arg), ops = ["Eq"], comps = [IName(id = "undefined")]), body = [
                            IAssign(
                                lvalue = [IName(id = arg)],
                                rvalue = IIfExp(
                                    cond = ICompare(
                                        lvalue = IGetAttr(
                                            base = pyargs_kw,
                                            attr = arg),
                                        comps = [IName(id = "undefined")],
                                        ops = ["Eq"]),
                                    body = self.comp(defaults[i]),
                                    orelse = IGetAttr(
                                        base = pyargs_kw,
                                        attr = arg)))]))
            js.append(IDelete(targets = [IGetAttr(base = pyargs_kw, attr = arg)]))

        if node.name in ("__getattr__", "__setattr__"):
            js.append(IName(id = "if (typeof %(id)s === 'string') { %(id)s = str(%(id)s); }" % { 'id': node.params.args[1] }))

        loopvar = self.alloc_var()

        if node.params.kwargs:
            js.append(IForEach(body = [
                        ICall(func = IGetAttr(base = IName(id = node.params.kwargs), attr = "PY$__setitem__"),
                              args = [
                                IName(id = node.params.kwargs),
                                ICall(func = IName(id = "str"), args = [IName(id = loopvar)]),
                                IGetItem(value = pyargs_kw, slice = IName(id = loopvar))])
                        ], target = IVar(name = loopvar), iter = pyargs_kw))

        js.extend(self.comp(node.body))

        if not (js and isinstance(js[-1], IReturn)):
            js.append(IReturn(expr = IName(id = "None")))

        self.scope = []

        exp = ILambda(body = js, name = node.name, params = IParameters(args = [], defaults = None, kwargs = None, varargs = None))

        for deco in reversed(node.decorators):
            exp = ICall(func = self.comp(deco), args = [exp])

        exp = ICall(func = IGetAttr(base = IName(id = '__builtins__'), attr = 'PY$function'), args = [exp])

        if self.destiny(["classdef", "function"], 1) in ["classdef"]:
            return exp
        else:
            return IVar(name = node.name, expr = exp)

    def node_boolop(self, node):
        assign_context = self.destiny(["assign", "function", "call", "comprehension"], 1) in ["assign", "call"]
        if assign_context:
            var = self.alloc_var()
            evallist = [ICompare(lvalue =
                                 ICall(func = IName(id = "bool"),
                                       args = [IAssign(lvalue = [IName(id = var)], rvalue = self.comp(val))]),
                                 ops = ["Eq"],
                                 comps = [IName(id = "True")])
                        for val in node.values]
            return ICall(func =
                         ILambda(body = [IVar(name = var),
                                         IBoolOp(op = node.op, values = evallist),
                                         IReturn(expr = IName(id = var))], params = None), args = [])
        else:
            return IBoolOp(values = [ICompare(lvalue = ICall(func = IName(id = "bool"), args = [self.comp(val)]), ops = ["Eq"], comps = [IName(id = "True")]) for val in node.values], op = node.op)

    def node_lambda(self, node):
        assert len(node.body) == 1
        return ILambda(params = self.comp(node.params), body = [IReturn(expr = self.comp(node.body[0]))])

    def node_augassign(self, node):
        if node.op == "Div":
            if self.future_division:
                op = "div"
            else:
                op = "floordiv"
        else:
            op = self.ops_augassign[node.op]

        func = "PY$__%s__" % op
        return self.assign_simple(node.target, self.purecall(node.target, func, node.value))

    def node_delete(self, node):
        return [self.delete_simple(part) for part in node.targets]

    def delete_simple(self, node):
        if isinstance(node, ist.GetItem):
            if isinstance(node.slice, ist.Slice):
                func = "PY$__delslice__"
                return self.purecall(node.value, func, node.slice.lower, node.slice.upper)
            else:
                func = "PY$__delitem__"
                return self.purecall(node.value, func, node.slice)
        elif isinstance(node, ist.GetAttr):
                return ICall(func = IGetAttr(base = IName(id = "$PY"), attr = "delattr"),
                             args = [self.comp(node.base), IString(value = node.attr)])
        elif isinstance(node, ist.Name):
            raise NotImplementedError("Javascript does not support deleting variables. Cannot compile")
        else:
            raise NotImplementedError("Unsupported delete type: %s" % node)

    def node_tryexcept(self, node):
        var = self.alloc_var()
        body = []
        catchall = False
        self.exceptions.append(var)

        lastif = None
        for i, n in enumerate(node.handlers):
            if n.name:
                if isinstance(n.name, IName):
                    vardecl = [IVar(name = n.name.id, expr = IName(id = var))]
                else:
                    raise JSError("Catching non-simple exceptions not supported")
            else:
                vardecl = []

            if n.type:
                exp = IIf(cond = ICall(func = IGetAttr(base = IName(id = "$PY"), attr = "isinstance"), args = [IName(id = var), self.comp(n.type)]), body = vardecl + self.comp(n.body))
                if lastif:
                    lastif.orelse = [exp]
                else:
                    body.append(exp)
                lastif = exp
            else:
                catchall = True
                if lastif:
                    lastif.orelse = self.comp(n.body)
                else:
                    body.append(self.comp(n.body))
            continue
        if not catchall:
            lastif.orelse = [IRaise(expr = IName(id = var))]

        node.body = self.comp(node.body)
        node.handlers = [ITryHandler(body = body, name = IName(id = var), type = None)]
        self.exceptions.pop()

        if node.orelse:
            else_var = self.alloc_var()
            node.handlers[0].body.insert(0, IAssign(lvalue = [IName(id = else_var)], rvalue = IName(id = "false")))
            res = [IVar(name = else_var, expr = IName(id = "true")), node, IIf(cond = IName(id = else_var), body = self.comp(node.orelse))]
            node.orelse = None
            return res
        else:
            return node

    def node_raise(self, node):
        if node.expr:
            node.expr = self.comp(node.expr)
        else:
            node.expr = IName(id = self.exceptions[-1])
        return node

    def node_global(self, node):
        self.scope.extend(node.names)
        return None

    def node_classdef(self, node):
        bases = [n.id for n in node.bases]
        if not bases:
            bases = ['object']
        if len(bases) == 0:
            raise NotImplementedError("Old-style classes not supported")
        elif len(bases) > 1:
            raise NotImplementedError("Multiple inheritance not supported")

        class_name = node.name

        use_prototypes = IName(id = "true")

        js = []

        inherit = ICall(func = IName(id = "__inherit"), args = [self.comp(IName(id = bases[0])), IString(value = class_name), use_prototypes])
        js.append(IVar(name = class_name, expr = inherit))

        self._class_name.append(class_name)

        for st in node.body:
            if isinstance(st, IAssign):
                value = self.comp(st.rvalue)
                for t in st.lvalue:
                    js.append(IAssign(lvalue = [IGetAttr(base = IName(id = class_name), attr = "PY$%s" % t.id)], rvalue = self.comp(st.rvalue)))
            elif isinstance(st, IFunction):
                js.append(IAssign(lvalue = [IGetAttr(base = IName(id = class_name), attr = "PY$%s" % st.name)], rvalue = self.comp(st)))
            elif isinstance(st, IClassDef):
                js.append(IAssign(lvalue = [IGetAttr(base = IName(id = class_name), attr = "PY$%s" % st.name)], rvalue = ICall(func = ILambda(body = self.comp(st) + [IReturn(expr = IName(id = st.name))], params = []), args = [])))
            elif isinstance(st, IString):
                js.append(IName(id = "\n".join(["/* %s */" % s for s in st.value.split("\n")])))
            elif isinstance(st, INop):
                pass
            else:
                raise NotImplementedError("Unsupported class data: %s" % st)

        self._class_name.pop()

        return js

    def make_listcomp(self, gen, comp):
        inner_body = []
        if isinstance(gen.target, ist.Name):
            for_target = gen.target.id
        elif isinstance(gen.target, ist.Tuple):
            for_target = self.alloc_var()
            for i, x in enumerate(gen.target.values):
                inner_body.append(IVar(name = x.id, expr = ICall(func = (IGetAttr(base = IName(id = for_target), attr = "PY$__getitem__")), args = [IName(id = for_target), INumber(value = i)])))
        else:
            raise JSError("Advanced for-loop decomposition not supported")

        innermost = inner_body
        itervar = self.alloc_var()
        for cond in gen.conds:
            innermost.append(self.comp(IIf(cond = cond, body = [])))
            innermost = innermost[-1].body

        body = []
        body.append(IVar(name = for_target, expr = None))
        body.append(IVar(name = itervar, expr = None))

        body.append(
            IFor(
                body = inner_body,
                init = IAssign(
                    lvalue = [IName(id = itervar)],
                    rvalue = ICall(func = IName(id = "iter"), args = [self.comp(gen.iter)])
                    ),
                cond = IAssign(lvalue = [IName(id = for_target)], rvalue = ICall(func = IGetAttr(base = IName(id = "$PY"), attr = "next"), args = [IName(id = itervar)])),
                incr = None
                )
            )
        return body, innermost

    def node_listcomp(self, node):
        comp = self.alloc_var()
        body, inner_body = self.make_listcomp(node.generators[0], comp)
        for gen in node.generators[1:]:
            next_body, next_inner_body = self.make_listcomp(gen, comp)
            inner_body.append(next_body)
            inner_body = next_inner_body

        inner_body.append(ICall(func = IGetAttr(base = IName(id = comp), attr = "push"), args = [self.comp(node.expr)]))
        body.insert(0, IVar(name = comp, expr = IList(values = [])))
        body.append(IReturn(expr = ICall(func = IName(id = "list"), args = [IName(id = comp)])))
        return ICall(func = ILambda(body = body, params = []), args = [])

    def node_generator(self, node):
        if self.emulate_generators:
            return self.node_listcomp(node)
        else:
            raise NotImplementedError("Cannot compile generator expressions")

    def node_comprehension(self, node):
        if isinstance(node.target, ast.Name):
            var = self.visit(node.target)
        elif isinstance(node.target, ast.Tuple):
            var = self.alloc_var()
        else:
            raise NotImplementedError("Unsupported target type in list comprehension")
