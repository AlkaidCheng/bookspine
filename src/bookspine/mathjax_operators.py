"""The TeX that MathJax 3.2.2 sets as a binary operator or a relation.

Written by scripts/write_mathjax_operators.py from MathJax's symbol tables and
operator dictionary; run it again when MathJax is upgraded.
https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/base/BaseMappings.ts
https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/ams/AmsMappings.ts
https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/core/MmlTree/OperatorDictionary.ts
"""

# Characters, as typed.
OPERATOR_CHARACTERS = frozenset("*+-:<=>")

# Control words that each stand for one symbol.
BINARY_OPERATOR_WORDS = frozenset("""
    Cap Cup amalg ast barwedge bigcirc bigtriangledown bigtriangleup boxdot boxminus
    boxplus boxtimes bullet cap cdot centerdot circ circledast circledcirc
    circleddash cup curlyvee curlywedge dagger ddagger diamond div divideontimes
    divsymbol dotplus doublebarwedge doublecap doublecup intercal land
    leftthreetimes lor ltimes mp notChar odot ominus oplus oslash otimes pm
    rightthreetimes rtimes setminus smallsetminus sqcap sqcup star times
    triangleleft triangleright uplus vartriangle vee veebar wedge wr
    """.split())
RELATION_WORDS = frozenset("""
    Bumpeq Doteq Join Leftarrow Leftrightarrow Lleftarrow Longleftarrow
    Longleftrightarrow Longrightarrow Lsh Rightarrow Rrightarrow Rsh Subset Supset
    Vdash Vvdash approx approxeq asymp backepsilon backsim backsimeq because between
    bowtie bumpeq circeq circlearrowleft circlearrowright cong curlyeqprec
    curlyeqsucc curvearrowleft curvearrowright dashleftarrow dashrightarrow dashv
    doteq doteqdot downdownarrows downharpoonleft downharpoonright eqcirc eqsim
    eqslantgtr eqslantless equiv fallingdotseq frown ge geq geqq geqslant gets gg
    ggg gggtr gnapprox gneq gneqq gnsim gt gtrapprox gtrdot gtreqless gtreqqless
    gtrless gtrsim gvertneqq hookleftarrow hookrightarrow in le leadsto leftarrow
    leftarrowtail leftharpoondown leftharpoonup leftleftarrows leftrightarrow
    leftrightarrows leftrightharpoons leftrightsquigarrow leq leqq leqslant
    lessapprox lessdot lesseqgtr lesseqqgtr lessgtr lesssim lhd ll lll llless
    lnapprox lneq lneqq lnsim longleftarrow longleftrightarrow longmapsto
    longrightarrow looparrowleft looparrowright lt lvertneqq mapsto mid models
    multimap nLeftarrow nLeftrightarrow nRightarrow nVDash nVdash ncong ne nearrow
    neq ngeq ngeqq ngeqslant ngtr ni nleftarrow nleftrightarrow nleq nleqq nleqslant
    nless nmid notin nparallel nprec npreceq nrightarrow nshortmid nshortparallel
    nsim nsubseteq nsubseteqq nsucc nsucceq nsupseteq nsupseteqq ntriangleleft
    ntrianglelefteq ntriangleright ntrianglerighteq nvDash nvdash nwarrow owns
    parallel perp pitchfork prec precapprox preccurlyeq preceq precnapprox precneqq
    precnsim precsim propto restriction rhd rightarrow rightarrowtail
    rightharpoondown rightharpoonup rightleftarrows rightleftharpoons
    rightrightarrows rightsquigarrow risingdotseq searrow shortmid shortparallel sim
    simeq smallfrown smallsmile smile sqsubset sqsubseteq sqsupset sqsupseteq subset
    subseteq subseteqq subsetneq subsetneqq succ succapprox succcurlyeq succeq
    succnapprox succneqq succnsim succsim supset supseteq supseteqq supsetneq
    supsetneqq swarrow therefore thickapprox thicksim to trianglelefteq triangleq
    trianglerighteq twoheadleftarrow twoheadrightarrow unlhd unrhd upharpoonleft
    upharpoonright upuparrows vDash varpropto varsubsetneq varsubsetneqq
    varsupsetneq varsupsetneqq vartriangleleft vartriangleright vdash
    """.split())

# Control words that make a binary operator or a relation of what follows.
OPERATOR_MAKING_WORDS = frozenset("""
    iff impliedby implies mathbin mathrel not stackbin stackrel
    """.split())
