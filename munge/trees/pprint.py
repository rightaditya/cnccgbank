from munge.util.list_utils import intersperse
    
def default_node_repr(node):
    if hasattr(node, 'category') and node.category is not None:
        if node.is_leaf():
            return "%s {%s} %s" % (node.tag, node.category, node.lex)
        else:
            return "%s {%s}" % (node.tag, node.category)
    else:
        if node.is_leaf():
            return "%s %s" % (node.tag, node.lex)
        else:
            return "%s" % node.tag
        
LeafCompressThreshold = 3 # Nodes with this number of all-leaf children will be printed on one line
def pprint_with(node_repr):
    def base_pprint(node, level=0, sep='   ', newline='\n', reduced_leaves=False):
        out = []
        if level == 0: 
            out.append('(')
        else: 
            out.append( sep * level )
    
        if node.is_leaf():
            if reduced_leaves:
                out.append(node_repr(node))
            else:
                out.append("(%s)" % node_repr(node))
        else:
            # special case for nodes with all-leaf children
            if node.count() <= LeafCompressThreshold and all(kid.is_leaf() for kid in node):
                out.append( "(%s %s)" % 
                    (node_repr(node), 
                    ' '.join([base_pprint(child, 0, sep, '', reduced_leaves=True) for child in node])) )
            else:
                out.append( "(%s%s" % (node_repr(node), newline) )
                out += intersperse([pprint(child, level+1, sep, newline) for child in node], newline)
                out.append( ")" )

        if level == 0:
            out.append(')')
        
        return ''.join(out)
        
    return base_pprint

pprint = pprint_with(default_node_repr)

if __name__ == '__main__':
    from munge.penn.parse import *
    import sys

    trees = parse_tree(sys.stdin.read(), AugmentedPennParser)
    for tree in trees:
        print pprint(tree, sep='  ')
        print
