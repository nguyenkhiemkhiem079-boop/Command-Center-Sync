import unittest,tempfile,sqlite3
from pathlib import Path
from contextlib import closing
from backup_registry import backup
class BackupIntegrityTests(unittest.TestCase):
    def test_actual_invalid_check_constraint_cannot_be_certified_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.db'
            with closing(sqlite3.connect(source)) as db:
                db.execute('CREATE TABLE t(x INTEGER CHECK(x>0))');db.execute('PRAGMA ignore_check_constraints=ON');db.execute('INSERT INTO t VALUES(-1)');db.commit()
            with self.assertRaisesRegex(RuntimeError,'SQLITE_BACKUP_INTEGRITY_FAILED'):backup(source,root/'backup')
            self.assertFalse(list((root/'backup').glob('*.json')))
            with closing(sqlite3.connect(source)) as db:self.assertEqual(db.execute('SELECT x FROM t').fetchone()[0],-1)
if __name__=='__main__':unittest.main()
