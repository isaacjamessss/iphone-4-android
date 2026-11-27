import subprocess

def GetGitCommit():
	try:
		ret = subprocess.check_output(
			['git', 'log', '-1', '--format=%h'],
			stderr=subprocess.DEVNULL)
		return ret.decode('ascii', 'replace').strip() or 'unknown'
	except Exception:
		return 'unknown'
Export('GetGitCommit')
