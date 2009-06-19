

def split_expr(token,text):
    '''looks for token in the expression text and splits the expression
    around the token and returns [token,textleft,textright] if found
    otherwise returns [text]. this routine is "quote" aware (won't
    match on tokens enclosed in quotes) and strips white space around
    l and r values'''
    i=text.find(token)
    j=text.find('"')
    if 0<=j<i:
        k=text[j+1:].find('"')
        if k>=0:
            l=text[k+j+2:].find(token)
            if l>=0:
                return [token,text[:k+j+l+2].strip(),text[k+j+l+2+len(token):].strip()]
        return [text.strip()]
    if i>=0:
        return [token,text[:i].strip(),text[i+len(token):].strip()]
    return [text.strip()]


def parse_expr(tokens,expr):
    '''converts a text representation of an expression into a parse
    tree using the grammar defined in tokens
    tokens define operations on l and r values
    tokens is a list of tuples in increasing order of precedence
      e.g. [('|',(bool.__or__,bool,bool)),('&',(bool.__and__,bool,bool)),('!',(_not,None,bool))]
    expr is a string: e.g. 'abc|de&fg'
    result is a nested list: e.g. [bool.__or__,'abc',[bool.__and__,'de',[_not,'','fg']]]
    run this program to see a complete example
    '''
    token=tokens[0][0]
    text=expr
    tree=split_expr(token,text)
    if len(tree)>1:
        tree[0]=tokens[0][1]
        tree[1]=parse_expr(tokens[:],tree[1])
        tree[2]=parse_expr(tokens[:],tree[2])
    else:
        if len(tokens)>1:
            token=tokens.pop(0)
            tree=parse_expr(tokens[:],expr)
        else:
            tree=expr.replace('"','')
    return tree

def call_tree(rtype,tree,conv,*args):
    '''
    calls the tree
    conv is the conversion dictionary the key is a tuple of types (fromtype, totype),
      the value is the conversion function taking the arguments l,r,args
    args is the set of caller defined arguments passed to the token callables
    '''
    if type(tree)!=str:
        l=call_tree(tree[0][1],tree[1],conv,*args)
        r=call_tree(tree[0][2],tree[2],conv,*args)
        return tree[0][0](l,r,*args)
    else:
#        tree=tree.replace('"','')
        if rtype and type(tree)!=rtype:
            return conv[(type(tree),rtype)](tree,*args)
        return tree


if __name__=='__main__':
    def contains_tag(l,r,*args):
        return True

    def is_viewed(l,r,*args):
        return False

    def is_selected(l,r,*args):
        return True

    def _not(l,r,*args):
        return not r

    def str2bool(val):
        return True
        return keyword_filter(item,val)

    converter={
    (str,bool):str2bool
    }

    print split_expr(' ','"abc de "f g')
    print split_expr(' ','"anc def" "ghu"')


    TOKENS=[
    (' ',(bool.__or__,bool,bool)),
    ('&',(bool.__and__,bool,bool)),
    ('|',(bool.__or__,bool,bool)),
    ('!',(_not,None,bool)),
    ('tag=',(contains_tag,None,str)),
    ('viewed',(is_viewed,None,None)),
    ('selected',(is_selected,None,None))
    ]

    ##sample expression tree 'abc def&ab|cd cd'
    exprs=(
    'samantha',
    'abc def&ab|cd cd',
    '!selected "selected"')


    for expr in exprs:
        print 'expression',expr
        tree=parse_expr(TOKENS[:],expr)
        print 'tree',tree
        print 'result',call_tree(bool,tree,converter)
