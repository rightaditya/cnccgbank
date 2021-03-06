# coding=utf-8
# Chinese CCGbank conversion
# ==========================
# (c) 2008-2012 Daniel Tse <cncandc@gmail.com>
# University of Sydney

# Use of this software is governed by the attached "Chinese CCGbank converter Licence Agreement"
# supplied in the Chinese CCGbank conversion distribution. If the LICENCE file is missing, please
# notify the maintainer Daniel Tse <cncandc@gmail.com>.

from __future__ import with_statement
from copy import copy

from munge.proc.filter import Filter
from munge.util.err_utils import warn, info, debug
from munge.util.deco_utils import memoised

from munge.trees.pprint import *
from munge.cats.nodes import *
from munge.cats.cat_defs import *
from munge.trees.traverse import nodes

from apps.util.echo import echo

from apps.cn.fix_utils import *
from apps.identify_lrhca import *
from apps.cn.output import OutputPrefacedPTBDerivation

use_bare_N = config.use_bare_N

def rename_category_while_labelling_with(label_function, node, substitute, when=None):
    '''Applies the labelling function _label_function_ to the given _node_, replacing
its category with _substitute_ before labelling, and re-instating the former category
afterwards, when the predicate _when_ is true for the node's category.'''
    if when and (not when(node.category)): return label_function(node)
    
    old_category = node.category
    node.category = substitute
    
    ret = label_function(node)
    
    node.category = old_category
    
    return ret
    
#@echo
def label_head_final(node):
    node.kids[0] = label(node[0])

    node[1].category = node.category | node[0].category
    node.kids[1] = label(node[1])

    return node
    
#@echo
def label_etc_head_final(node):
    node.kids[0] = label(node[0])

    node[1].category = featureless(node.category) | featureless(node[0].category)
    node.kids[1] = label(node[1])

    return node

#@echo
def label_head_initial(node):
    node.kids[1] = label(node[1])

    node[0].category = node.category / node[1].category
    node.kids[0] = label(node[0])

    return node

label_predication = label_head_final

#@echo
def label_left_absorption(node):
    node[0].category = ptb_to_cat(node[0])
    
    node[1].category = node.category
    node.kids[1] = label(node[1])
    
    return node

#@echo
def label_right_absorption(node):
    node[1].category = ptb_to_cat(node[1])
    
    node[0].category = node.category
    node.kids[0] = label(node[0])
    
    return node

#@echo
def label_adjunction(node):
    if has_tag(node, 'h') or node.tag.find(':') == -1:
        node[1].category = ptb_to_cat(node[1], return_none_when_unmatched=True, return_none_when_vp=True, return_none_when_exactly_vp=True) or node.category
    else:
        node[1].category = ptb_to_cat(node[1], return_none_when_unmatched=True, return_none_when_vp=True) or node.category
    node.kids[1] = label(node[1])
    
    node[0].category = featureless(node.category) / featureless(node[1].category)
    node.kids[0] = label(node[0])
    
    return node

#@echo
def label_np_structure(node):
    node[0].category = featureless(node.category) / featureless(node.category)
    node.kids[0] = label(node[0])
    if node.count() > 1:
        node[1].category = node.category
        node.kids[1] = label(node[1])
    
    return node

#@echo
def label_right_adjunction(node):
    #node[0].category = ptb_to_cat(node[0], return_none_when_unmatched=True) or node.category
    node[0].category = node.category
    node.kids[0] = label(node[0])
    
    no_features = featureless(node.category)
    #node[1].category = no_features | featureless(node[0].category)
    node[1].category = no_features | no_features
    node.kids[1] = label(node[1])
    
    return node

#@echo
def label_coordination(node, inside_np=False, ucp=False):
    if use_bare_N:
        top_level_category = N if (not ucp and node.category == NP) else node.category
    else:
        top_level_category = NP if (not ucp and node.category == NP) else node.category

    node[0].category = ptb_to_cat(node[0]) if ucp else top_level_category # node.category
    # for UCP, if node[0]'s tag suggests NP or N (0:80(22)), then use top_level_category instead
    if ucp and node[0].category in (NP, N):
        node[0].category = top_level_category
        
    node.kids[0] = label(node[0], inside_np)
    
    node[1].category = top_level_category # node.category
    # Label then apply [conj], so that kid categories don't inherit the feature
    node.kids[1] = label(node[1])
    node[1].category = top_level_category.clone_adding_feature('conj')
    
    return node

#@echo
def label_partial_coordination(node, inside_np=False, ucp=False):
    node[0].category = ptb_to_cat(node[0])
    node.kids[0] = label(node[0], inside_np)
    
    debug('label_partial_coordination node.category: %s, %s', node.category, node)
    node[1].category = ptb_to_cat(node[1]) if ucp else node.category 
    node.kids[1] = label(node[1], inside_np)
    
    return node
    
#@echo
def label_np_internal_structure(node):
    if use_bare_N and node.category == NP:
        P = NP
    else:
        P = node.category
    
    for kid in node:
        # :r to ensure correct analysis in e.g. 0:86(3)
        if has_tags(kid, 'Nhr'):
            kid.category = P
        elif has_tag(kid, 'n') or \
             kid.tag.startswith('CD') or \
             kid.tag.startswith('OD'):
            kid.category = P/P
        elif kid.tag == 'CC':
            kid.category = conj
        elif kid.tag.startswith('NP'):
            kid.category = P
        else:
            kid.category = np_modifier_tag_to_cat(kid.tag)
    
    if node.count() == 1:
        node.category = node[0].category
    
    node.kids[0] = label(node[0])
    if node.count() > 1:
        node.kids[1] = label(node[1])
    
    return node

# If no process successfully assigns a category, these are used to map PTB tags to
# a 'last-ditch' category.

# If we are using N->NP, then map lexical nouns and their modifiers to N. Otherwise, map them to NP.
BareN = N if use_bare_N else NP
BareNfN = NfN if use_bare_N else NPfNP
Map = {
    'NP': NP, 'PN': NP,
    'DT': NP,
    'NT': NP,
    
    'NN': BareN, 'NR': BareN,
    
    'FRAG': Sfrg,
    'IP': Sdcl,
    'CP-Q': Sq,
    
    'ADVP': SbNPfSbNP,
    'AD': SbNPfSbNP,
    
    'VP': SdclbNP, 
    'VA': SdclbNP, 'VV': SdclbNP,
    # not really intended for use. FLR < VE (see the "Addendum to the Bracketing Guidelines for the ACE Chinese Broadcast News Data")
    # appears in 25:97(2). We'll just treat this as a noisy unary rule.
    'VE': SdclbNP,
#    'VC': SdclbNPfNP,
    
    'VSB': SdclbNP, 'VRD': SdclbNP, 'VCD': SdclbNP, 'VNV': SdclbNP, 'VPT': SdclbNP,
    'CC': conj,
    
    'CD': QP,
    # to account for noise in 25:43(4)
    'OD': QP,
    
    'ADJP': BareNfN,
    'JJ': BareNfN,
    # to account for CLP modification (the modifiers should end up as M/M, see 0:9(3))
    'CLP': C('M'),
    
    'DP-TPC': NP, # DP-TPC in 0:13(9)
    'DP': BareN,
    'DNP': BareNfN,
    
    'FW': BareN, # last ditch for filler words
    
    'CP-PRD': NP,
    'CP-OBJ': Sdcl, # 8:16(9) CP in object position is treated as IP
    'CP-CND': SfS,
    'CP-ADV': SfS,
}

PunctuationMap = {
    '.': '.', # Roman period
    '。': '.', # Chinese period
    
    # Enumeration comma (顿号) for separating list items
    # usually, this maps to the category conj, but there are derivations with
    # underspecified ('funny') coordination structure involving the enumeration comma (0:57(12)).
    # Since we can't treat these as conj, we simply treat them as absorption, in
    # line with funny conj.
    '、': ',',
    
    '，': ',', # Clausal comma (逗号)
    ',': ',', # Roman comma
    
    '？': '.', '?': '.', # Chinese question mark
    '！': '.', '!': '.', # Chinese exclamation mark
    
    '：': ':', ':': ':', # Chinese colon
    '；': ';', ';': ';', # Chinese semicolon
    
    '（': 'LRB', '(': 'LRB', # Chinese opening paren
    '）': 'RRB', ')': 'RRB', # Chinese closing paren
    
    '“': 'LQU', '”': 'RQU', # Roman double quote
    '‘': 'LQU', '’': 'RQU', # Roman single quote
    '`': 'LQU', # ASCII backtick, used as opening quote in 7:2(24)
    '＇': 'RQU', # full width apostrophe, used as close quote
    
    '—': '.', # Chinese dash

    '〈': 'LRB', '〉': 'RRB', # Chinese single bracket    
    '〈': 'LRB', '〉': 'RRB', # Chinese single bracket
    '《': 'LRB', '》': 'RRB', # Chinese title bracket
    '『': 'LRB', '』': 'RRB', # Chinese double corner bracket
    '「': 'LRB', '」': 'RRB', # Chinese left corner bracket
    '＜': 'LRB', '＞': 'RRB', # these turn up in 6:40(10)
    
    '/': '.', '//': '.',
}

Dashes = frozenset("── - --- ---- ━ ━━ — —— ———".split())
def is_dashlike(t):
    return t in Dashes
    
@memoised
def make_atomic_category(atom):
    return AtomicCategory(atom)
    
RootMap = {
    'CP': Sdcl,
    'IP': Sdcl,
    'CP-Q': Sq,
}

#@echo
def ptb_to_cat(node, return_none_when_unmatched=False, is_root=False, return_none_when_vp=False, return_none_when_exactly_vp=False):
    '''Given _node_, returns a category object based only on its treebank
tag, using the mapping. If _return_none_when_unmatched_ is True, None is
returned if the mapping yields no category; otherwise, an atomic category
is returned with the base CPTB tag. If _is_root_, a special mapping is
consulted first.'''
    # See label_adjunction. If we have IP < IP-SBJ VP, we want the VP node to receive S[dcl]\S[dcl],
    # not S[dcl]\NP (what it would receive if Map was consulted). See 5:35(1) for an example.
    # For all other cases (a VP argument, for instance), we want the mapping VP -> S[dcl]\NP to hold
    if return_none_when_vp and (has_verbal_tag(node) or (return_none_when_exactly_vp and node.tag.startswith('VP'))): return None
    
#    if node.tag.find('-PRD') != -1: return make_atomic_category('PE')
    if node.tag in ('PU', 'CSC') and node.is_leaf():
        # map dunhao to category conj only when it's the left child
        # (some noise cases or mis-annotations like 10:43(25))
        # TODO: find a better way to do the lch test
        if node.lex == '、' and (node.parent and node.parent[0] == node): 
            return conj
        if node.lex in PunctuationMap:
            return make_atomic_category(PunctuationMap[node.lex])
        elif is_dashlike(node.lex):
            return make_atomic_category('.')
        else:
            return make_atomic_category(',')
            
    # CP ending in SP (5:95(30)) should be treated as IP
    if node.tag.startswith("CP") and node[-1].tag.startswith("SP"):
        return Sdcl
        
    # Without this, adjuncts of NP-PRD get (S\NP)/NP instead of (S\NP)/(S\NP) because Map is being consulted (10:68(21))
    # However, check that we don't have:
    #         VP
    #        /  \
    #       VC   NP-PRD
    # in which case let NP-PRD -> category NP go through (0:58(8))
    if (node.tag.startswith('NP') and node.tag.find('-PRD') != -1 and
        not node.parent[0].tag.startswith('VC')):
        return SdclbNP
    
    original_tag = base_tag(node.tag, strip_cptb_tag=False)
    stemmed_tag = base_tag(node.tag)
    
    # TODO: copy on write Categories? categories are (meant to be) immutable but their slots aren't
    return copy((is_root and (RootMap.get(original_tag, None) or RootMap.get(stemmed_tag, None)))
             or Map.get(original_tag, None)
             or Map.get(stemmed_tag, None if return_none_when_unmatched else AtomicCategory(stemmed_tag)))

NPModifierMap = {
    'CP': C('NP/NP'),
}
def np_modifier_tag_to_cat(ptb_tag):
    ptb_tag = base_tag(ptb_tag)
    return copy(NPModifierMap.get(ptb_tag, None))

def is_cp_to_np_nominalisation(node):
    return (node.count() == 1 and
            node.tag.startswith('NP') and
            (node[0].tag.startswith('CP') or node[0].tag.startswith("DNP")))

def is_PRO_trace(node):
    return (node.count() >= 2 and node[0].count() == 1
            and node[0][0].tag == "-NONE-"
            and node[0][0].lex == "*PRO*")
            
def is_punctuation_headed(node):
    return node[1].tag == 'PU:h'

#@echo
def label(node, inside_np=False):
    '''
    Labels the descendants of _node_ and returns _node_.
    '''
    global BareN
    
    if node.category is None:
        node.category = ptb_to_cat(node)
        
        # if this matches the IP root with a *PRO* trace under it, then
        # we shouldn't map IP -> S, but rather IP -> S\NP
        if node.tag.startswith('NT'): # map NT -> NP, not N
            node.category = NP
        elif has_noun_tag(node):
            node.category = BareN
        else:
            node.category = ptb_to_cat(node)
    
    if node.is_leaf():
        if not node.category:
            node.category = ptb_to_cat(node)
        return node
    
    # NP/NP (CP) -> NP
    elif is_cp_to_np_nominalisation(node):
        node[0].category = NPfNP
        node.kids[0] = label(node[0])
        
        return node
    
    # VSB is analysed as head-final
    elif node.tag.startswith('VSB'):
        node[1].category = node.category
        node.kids[1] = label(node[1])
        
        node[0].category = featureless(node.category) / featureless(node[1].category)
        node.kids[0] = label(node.kids[0])
        
        return node
        
    # VCD is treated like apposition
    elif node.tag.startswith('VCD'):
        if has_verbal_tag(node[0]):
            node[0].category = node.category
        else:
            node[0].category = ptb_to_cat(node[0])
            
        node.kids[0] = label(node[0])
            
        if has_verbal_tag(node[1]):
            node[1].category = node.category
        else:
            node[1].category = ptb_to_cat(node[1])
            
        node.kids[1] = label(node[1])
            
        return node
        
    elif node.tag.startswith('VRD'):
        return label_right_adjunction(node)

    # must be above is_apposition, because there exist NP-APP:a ETC:& cases
    elif is_etc(node):
        return label_etc_head_final(node)
        
    elif is_S_NP_apposition(node):
        return rename_category_while_labelling_with(label_head_final, node, BareN if node.category == NP else node.category)
        
    elif (node.count() == 1
       or is_topicalisation(node)
       or is_topicalisation_without_gap(node)
       or is_apposition(node)
       or is_argument_cluster(node)
       or is_modification(node)):
        
        node.kids[0] = label(node[0])
        if node.count() > 1:
            node.kids[1] = label(node[1])
        
        return node
    
    elif is_partial_ucp(node):
        return label_partial_coordination(node, ucp=True)
    elif is_ucp(node):
        return label_coordination(node, ucp=True)
        
    elif is_predication(node):
        return label_predication(node)

    elif is_left_absorption(node):
        return label_left_absorption(node)
    elif is_right_absorption(node):
        return label_right_absorption(node)
        
    elif is_right_adjunction(node): # (:h :a), for aspect particles
        return label_right_adjunction(node)
        
    elif is_partial_coordination(node):
        return label_partial_coordination(node)
    elif is_coordination(node):
        return label_coordination(node)
    
    elif is_np_structure(node):# and not node[0].tag.startswith('IP-APP'):
        return rename_category_while_labelling_with(
            label_np_structure,
            node, BareN,
            when=lambda category: category == NP)
    
    elif is_np_internal_structure(node):
        return label_np_internal_structure(node)
        
    elif is_punctuation_headed(node):
        return label_head_final(node)
    
    elif is_adjunction(node):
        return label_adjunction(node)
    
    elif is_head_final(node):
        return label_head_final(node)
    elif is_head_initial(node):
        return label_head_initial(node)
    
    else:
        warn("Node did not match any known patterns -- assuming adjunction: %s",
            node.__repr__(suppress_lex=True))
        return label_adjunction(node)

rewrite_lcp_as_np = config.rewrite_lcp_as_np

def label_root(root):
    root.category = ptb_to_cat(root, is_root=True)
    
    for node in nodes(root):
        # remove PRO traces as a preprocessing step
        if is_PRO_trace(node):
            # We choose not to shrink *PRO* traces IP-SBJ < NP-SBJ(*PRO*) VP to avoid
            # category proliferation (11:22(24))
            # These *PRO* traces just get removed later as if they were *pro* traces (fix_prodrop in fix_rc.py)
            if node.tag.startswith('IP-SBJ') and node[0].tag.startswith('NP-SBJ'): continue
            # Similarly for IP(*PRO* VP) when it occurs in UCP (7:98(16), 0:83(11))
            if node.tag.startswith('IP') and has_tag(node, 'C'): continue
            
            if node.parent is None: continue
            
            # Avoid generating LCP\S[dcl] and LCP\(S[dcl]\NP) categories (annotation seems to be inconsistent 6:31(4), 4:50(4))
            if node.tag.startswith('IP') and node.parent.tag.startswith('LCP'): continue
            if node.tag.startswith('IP') and node.parent.tag.startswith('PP'): continue
            if rewrite_lcp_as_np and node.tag.startswith('IP') and node.parent.tag.startswith('NP'): continue
            
            # However, if we have IP(*PRO* VP) at the root, treat as pro-drop to eliminate S\NP as a root category
            
            old_tag = node.tag
            
            new_node = shrink_left(node, node.parent)
            new_node.tag = base_tag(new_node.tag, strip_cptb_tag=False)
            
            if not node.parent:
                root = new_node

            inherit_tag(new_node, node)
            
            # If we have something like
            # IP-APP(LPA (IP-APP (IP-APP (*PRO* VP) RPA)))
            # after PRO trace removal we want
            # VP-APP (LPA VP-APP (VP-APP RPA)) (cf 10:3(39))
            cur = new_node.parent
            while cur and cur.tag == old_tag:
                cur.tag = new_node.tag
                cur = cur.parent
        
    return label(root)

class LabelNodes(Filter, OutputPrefacedPTBDerivation):
    def __init__(self, outdir):
        Filter.__init__(self)
        OutputPrefacedPTBDerivation.__init__(self, outdir)
    
    def accept_derivation(self, bundle):
        bundle.derivation = label_root(bundle.derivation)
        
        self.write_derivation(bundle)
    
    opt = '3'
    long_opt = 'label'
    
    arg_names = 'OUTDIR'
