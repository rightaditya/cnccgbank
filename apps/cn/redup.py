from munge.proc.filter import Filter
from munge.cats.trace import analyse
from munge.util.dict_utils import CountDict, sorted_by_value_desc
from munge.trees.traverse import nodes
from munge.util.err_utils import *
from collections import defaultdict

from apps.cn.tag import is_coordination
from apps.identify_lrhca import base_tag

from collections import defaultdict

def aabb(l):
    return len(l) == 4 and l[0] == l[1] and l[2] == l[3]

def abab(l):
    return len(l) == 4 and l[0] == l[2] and l[1] == l[3]
    
def aab(l):
    return len(l) == 3 and l[0] == l[1]

class RedupAnalysis(Filter):
    def __init__(self):
        Filter.__init__(self)
        self.conjs = defaultdict(lambda: defaultdict(int))
        
    def accept_leaf(self, leaf):
        l = leaf.lex.decode('u8')
        if aabb(l): print 'aabb', leaf.lex
        elif abab(l): print 'abab', leaf.lex
        elif aab(l): print 'aab', leaf.lex
