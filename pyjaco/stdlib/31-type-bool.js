/**
  Copyright 2011-2013 Christian Iversen <chrivers@iversen-net.dk>

  Permission is hereby granted, free of charge, to any person
  obtaining a copy of this software and associated documentation
  files (the "Software"), to deal in the Software without
  restriction, including without limitation the rights to use,
  copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the
  Software is furnished to do so, subject to the following
  conditions:

  The above copyright notice and this permission notice shall be
  included in all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
  OTHER DEALINGS IN THE SOFTWARE.
**/

var bool = __inherit(int, "bool");

__builtins__.PY$bool = bool;

bool.PY$__init__ = function(self, b) {
    if (b) {
        self.obj = 1;
    } else {
        self.obj = 0;
    }
};

bool.PY$__hash__ = function (self) {
    return self.obj === 0 ? $c0 : $c1;
};

bool.PY$__str__ = function (self) {
    if (self.obj) {
        return str("True");
    } else {
        return str("False");
    }
};

bool.toString = function() {
    if (this.obj) {
        return "1";
    } else {
        return "";
    }
};

bool.PY$__hash__ = function(self) {
    return self.obj === 0 ? $c0 : $c1;
};

bool.PY$__repr__ = bool.PY$__str__;

bool.PY$__eq__ = function(self, other) {
    if (self.PY$__class__ === undefined) {
        return object.PY$__eq__(self, other);
    } else if (other.PY$__int__ !== undefined) {
        return Number(self.obj) === other.PY$__int__(other)._js_() ? True : False;
    } else {
        return self.obj === other.obj ? True : False;
    }
};

bool._js_ = function() {
    if (this.obj) {
        return true;
    } else {
        return false;
    }
};

bool.PY$__neg__ = function(self) {
    return self.obj ? False : True;
};

bool.PY$__nonzero__ = function(self) {
    return self.obj ? True : False;
};

bool.PY$__int__ = function(self) {
    if (self.obj) {
        return $c1;
    } else {
        return $c0;
    }
};

var True = bool(true);
var False = bool(false);

__builtins__.PY$True = True;
__builtins__.PY$False = False;

bool.PY$__create__ = function(cls, b) {
    if (b === null || b === undefined) {
        return False;
    } else if (b.PY$__nonzero__ != undefined) {
        return b.PY$__nonzero__(b);
    } else if (b.PY$__len__ != undefined) {
        var len = b.PY$__len__(b);
        return len.PY$__gt__(len, $c0);
    } else if (b instanceof Array) {
        if (b.length) {
            return True;
        } else {
            return False;
        }
    } else if (typeof b === 'object') {
        for (var i in b) {
            return True;
        }
        return False;
    } else {
        if (!!b) {
            return True;
        } else {
            return False;
        }
    }
};
