import os,subprocess,tempfile,unittest
from pathlib import Path
@unittest.skipUnless(os.name=='nt','Windows DACL integration')
class PrivateAclTests(unittest.TestCase):
    def test_explicit_everyone_removed_and_content_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'fixture-token.txt';target.write_text('TEST_ONLY_NOT_A_CREDENTIAL')
            ps="$p='"+str(target).replace("'","''")+"';$a=Get-Acl -LiteralPath $p;$s=[Security.Principal.SecurityIdentifier]::new('S-1-1-0');$r=[Security.AccessControl.FileSystemAccessRule]::new($s,'Read','Allow');$a.AddAccessRule($r);Set-Acl -LiteralPath $p -AclObject $a"
            subprocess.run(['pwsh','-NoProfile','-Command',ps],capture_output=True,check=True)
            helper=Path(__file__).resolve().parents[1]/'scripts/protect-private-path.ps1'
            result=subprocess.run(['pwsh','-NoProfile','-File',str(helper),'-LiteralPath',str(target)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PRIVATE_DACL_VERIFIED',result.stdout)
            self.assertEqual(target.read_text(),'TEST_ONLY_NOT_A_CREDENTIAL')
    def test_junction_ancestor_refused(self):
        with tempfile.TemporaryDirectory() as folder,tempfile.TemporaryDirectory() as outside:
            target=Path(outside)/'fixture.txt';target.write_text('TEST_ONLY')
            link=Path(folder)/'junction'
            subprocess.run(['cmd','/c','mklink','/J',str(link),outside],capture_output=True,check=True)
            try:
                helper=Path(__file__).resolve().parents[1]/'scripts/protect-private-path.ps1'
                result=subprocess.run(['pwsh','-NoProfile','-File',str(helper),'-LiteralPath',str(link/'fixture.txt')],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertIn('reparse ancestor',result.stderr)
                self.assertEqual(target.read_text(),'TEST_ONLY')
            finally:os.rmdir(link)
if __name__=='__main__':unittest.main()
