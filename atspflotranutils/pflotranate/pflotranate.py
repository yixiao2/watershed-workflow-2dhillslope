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
    # Dynamically resolve `path` relative to pflotranate.py
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Directory of pflotranate.py
    pflotran_components_dir = os.path.join(script_dir, 'pflotran_components')
    
    with open(fout) as f:
        t = ''
        inside_pk_tree = False
        inside_water_balance = False
        nesting_level = 0
        cycledriver_content = ''  # Store content from cycledriver-pktree.xml

        # Read all lines from cycledriver-pktree.xml upfront
        with open(os.path.join(pflotran_components_dir, 'cycledriver-pktree.xml')) as g:
            cycledriver_content = g.readlines()  # Read as a list of lines
        
        for line in f:
            line_handled_flag = False
            if 'name="PK tree"' in line:
                t += line  # Add the line
                line_handled_flag = True  # Mark line as handled
                inside_pk_tree = True
                # Append the first part of cycledriver (Header + flow and transport)
                for pktree_line in cycledriver_content[:-1]:  # Add flow and transport, but exclude last line of "</ParameterList>"
                    t += pktree_line

            if inside_pk_tree:
                # Detect start of "water_balance"
                if '<ParameterList name="water_balance"' in line:
                    #t += ''.join('  ' + line)  # Add the line
                    #line_handled_flag = True  # Mark line as handled
                    inside_water_balance = True
                    nesting_level = 1  # Initialize the nesting level for this block
                    #continue
                
                # Inside "water_balance", accumulate the entire block
                if inside_water_balance:
                    # Update nesting level for nested ParameterList tags
                    if '<ParameterList' in line:
                        nesting_level += 1
                    if '</ParameterList>' in line:
                        nesting_level -= 1
                    # When exiting the outermost "water_balance" block
                    if nesting_level == 0:
                        inside_water_balance = False
                        inside_pk_tree = False # Exit "PK tree" section
                        t += ''.join('  ' + line)  # Add the line
                        line_handled_flag = True  # Mark line as handled
                        t += '</ParameterList>\n' # Add back "</ParameterList>" excluded above
                    else:
                        t += ''.join('  ' + line)  # Add the line
                        line_handled_flag = True  # Mark line as handled
                    continue

            if 'name="PKs"' in line:
                t += line  # Add the line
                line_handled_flag = True  # Mark line as handled
                with open(os.path.join(pflotran_components_dir, 'pks.xml')) as g:
                    for pks in g:
                        t += pks
            if 'name="evaluators"' in line:
                t += line  # Add the line
                line_handled_flag = True  # Mark line as handled
                with open(os.path.join(pflotran_components_dir, 'state-evals.xml')) as g:
                    for fieldeval in g:
                        t += fieldeval
            if 'name="initial conditions"' in line:
                t += line  # Add the line
                line_handled_flag = True  # Mark line as handled
                with open(os.path.join(pflotran_components_dir, 'state-ics.xml')) as g:
                    for ics in g:
                        t += ics
            if 'name="observations"' in line:
                t += line  # Add the line
                line_handled_flag = True  # Mark line as handled
                with open(os.path.join(pflotran_components_dir, 'obs.xml')) as g:
                    for obs in g:
                        t += obs
            
            # Add any unhandled lines to `t` by default
            if not line_handled_flag:
                t += line
                
    with open(fout, 'w') as f:
        f.write(t)
    print(f"{fout} generated (2/3)")
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

