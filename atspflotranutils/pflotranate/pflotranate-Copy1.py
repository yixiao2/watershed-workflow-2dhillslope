'''add pflotran components to ats-only xml file
now only support cybernetic reaction network
example: python pflotranate.py ats.xml
'''

import os
import sys
import glob

def get_fin():
    if len(sys.argv) == 1:
        print('input xml file not defined')
        print('example: python '+sys.argv[0]+' ats.xml')
        fl = glob.glob('*.xml')
        print('working dir has '+str(len(fl))+' xml files:')
        for i, f in enumerate(fl):
            print(str(i+1).zfill(2)+' : '+f)
        sys.exit(1)
    elif len(sys.argv) == 2:
        fin = sys.argv[1]
        if not os.path.exists(fin):
            print(fin+' does not exist')
            fl = glob.glob('*.xml')
            print('working dir has '+str(len(fl))+' xml files:')
            for i, f in enumerate(fl):
                print(str(i+1).zfill(2)+' : '+f)
            sys.exit(1)
    else:
        print('too many args')
        print('example: python '+sys.argv[0]+' ats.xml')
        sys.exit(1)
    return fin

def reorganize_fin(fin):
    with open(fin) as f:
        indent = 0
        t = ''
        for i, line in enumerate(f):
            if 'chemistry' in line:
                print('found \'chemistry\' in this xml file')
                print('no need to pflotranate')
                sys.exit(1)
            if indent < 0:
                print('indent < 0')
                print('closing tag error at line '+str(i+1))
                print(line)
                sys.exit(1)
            if line.strip().startswith('<ParameterList'):
                t += ' '*indent+line.strip()+'\n'
                indent += 2
            elif line.strip().startswith('</ParameterList'):
                indent -= 2
                t += ' '*indent+line.strip()+'\n'
            elif line.strip().startswith('<Parameter'):
                t += ' '*indent+line.strip()+'\n'
    fout = fin.split('.xml')[0]+'_pflotran.xml'
    with open(fout, 'w') as f:
        f.write(t)
    print(fout+' generated (1/3)')
    return fout

def add_pflotran_components(fout, path):
    with open(fout) as f:
        t = ''
        for line in f:
            t += line
            if 'name=\"PK tree\"' in line:
                with open(os.path.join(path, 'cycledriver-pktree.xml')) as g:
                    for pktree in g:
                        t += pktree
            if 'name=\"PKs\"' in line:
                with open(os.path.join(path, 'pks.xml')) as g:
                    for pks in g:
                        t += pks
            if 'name=\"evaluators\"' in line:
                with open(os.path.join(path, 'state-evals.xml')) as g:
                    for fieldeval in g:
                        t += fieldeval
            if 'name=\"initial conditions\"' in line:
                with open(os.path.join(path, 'state-ics.xml')) as g:
                    for ics in g:
                        t += ics
            if 'name=\"observations\"' in line:
                with open(os.path.join(path, 'obs.xml')) as g:
                    for obs in g:
                        t += obs
    with open(fout, 'w') as f:
        f.write(t)
    print(fout+' generated (2/3)')
    return fout
    
def reorganize_fout(fout):
    with open(fout) as f:
        indent = 0
        t = ''
        for i, line in enumerate(f):
            if indent < 0:
                print('indent < 0')
                print('closing tag error at line '+str(i+1))
                print(line)
                sys.exit(1)
            if line.strip().startswith('<ParameterList'):
                t += ' '*indent+line.strip()+'\n'
                indent += 2
            elif line.strip().startswith('</ParameterList'):
                indent -= 2
                t += ' '*indent+line.strip()+'\n'
            elif line.strip().startswith('<Parameter'):
                t += ' '*indent+line.strip()+'\n'
    with open(fout, 'w') as f:
        f.write(t)
    print(fout+' generated (3/3)')
    return fout

if __name__ == '__main__':
    reorganize_fout(add_pflotran_components(reorganize_fin(get_fin()), './pflotran_components'))

