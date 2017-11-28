import subprocess

proc = subprocess.Popen(
    ['python', '-c', 'import pkg_resources; pkgs = [ (p.key, p.version) for p in pkg_resources.working_set]; print pkgs'],
    #['sh', '-c', 'pip list'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE)
output, err = proc.communicate()

if output:
    print output
