"""Exercise overlapping block moves and preservation of unrelated GPT fields."""
import importlib.util
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

spec=importlib.util.spec_from_file_location('grow_app',Path(__file__).with_name('grow-app-offline.py'))
grow=importlib.util.module_from_spec(spec);spec.loader.exec_module(grow)


class Tests(unittest.TestCase):
    def test_ram_epoch_clock_is_rejected_before_filesystem_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            device=Path(directory)/'filesystem.bin'
            image=bytearray(2048)
            struct.pack_into('<I',image,1024+44,1792083216)
            struct.pack_into('<I',image,1024+64,1737633720)
            device.write_bytes(image)
            with patch.object(grow.time,'time',return_value=252):
                with self.assertRaisesRegex(AssertionError,'RAM clock'):
                    grow.check_filesystem_clock(device)
            with patch.object(grow.time,'time',return_value=1792083216):
                grow.check_filesystem_clock(device)

    def test_secondary_array_requires_eight_sectors_for_29_entries(self):
        table=bytes(29*128)
        last=grow.SIZE//512-1
        def header(current,other,entries):
            sector=bytearray(512)
            struct.pack_into('<8s4I4Q16sQ3I',sector,0,b'EFI PART',0x10000,92,0,0,
                             current,other,4096,30773247,bytes(range(16)),entries,29,128,zlib.crc32(table))
            return grow.replace_header_crc(sector,table)
        for start,valid in ((last-8,True),(last-7,False)):
            captured={(510,2):b'\x55\xaa',(512,512):header(1,last,2),
                      (last*512,512):header(last,1,start),
                      (1024,len(table)):table,(start*512,len(table)):table}
            with self.subTest(start=start),patch.object(grow,'read_at',side_effect=lambda stream,offset,count:captured[offset,count]):
                if valid:self.assertEqual(grow.read_gpt(None)[1],table)
                else:
                    with self.assertRaisesRegex(AssertionError,'overlaps'):
                        grow.read_gpt(None)

    def test_moves_match_original_bytes_with_overlap_and_short_final_chunk(self):
        original=random.Random(124).randbytes(8192)
        for source,destination,size,chunk in ((0,1,4096,257),(101,602,3000,511),(13,5000,2001,256)):
            with self.subTest(source=source,destination=destination),tempfile.TemporaryFile('w+b') as stream:
                stream.write(original);stream.flush()
                checkpoints=[]
                grow.move_backwards(stream,source,destination,size,lambda *args:checkpoints.append(args),chunk)
                expected=bytearray(original)
                expected[destination:destination+size]=original[source:source+size]
                stream.seek(0);self.assertEqual(stream.read(),expected)
                self.assertEqual(checkpoints[-1][0],0)
                self.assertEqual(sum(entry[1] for entry in checkpoints),size)

    def test_interruption_leaves_uncopied_lower_source_intact(self):
        original=random.Random(696).randbytes(4096)
        with tempfile.TemporaryFile('w+b') as stream:
            stream.write(original);stream.flush()
            points=[]
            def checkpoint(*args):
                points.append(args)
                if len(points)==3:raise RuntimeError('simulated interruption')
            with self.assertRaisesRegex(RuntimeError,'interruption'):
                grow.move_backwards(stream,0,100,2049,checkpoint,256)
            remaining=points[-1][0]
            self.assertEqual(grow.read_at(stream,0,remaining),original[:remaining])
            self.assertEqual(grow.read_at(stream,100+remaining,2049-remaining),original[remaining:2049])

    def test_reject_invalid_direction_before_writing(self):
        with tempfile.TemporaryFile('w+b') as stream:
            stream.write(b'unchanged');stream.flush()
            for source,destination,size in ((0,0,1),(2,1,1),(0,1,0)):
                with self.assertRaises(AssertionError):
                    grow.move_backwards(stream,source,destination,size,lambda *args:None)
            stream.seek(0);self.assertEqual(stream.read(),b'unchanged')

    def test_only_partition_bounds_and_header_crcs_change(self):
        table=bytearray(random.Random(3).randbytes(32*128))
        for number,name,start,sectors in grow.OLD:
            offset=(number-1)*128
            table[offset+56:offset+128]=name.encode('utf-16-le').ljust(72,b'\0')
            struct.pack_into('<QQ',table,offset+32,start,start+sectors-1)
        changed=grow.replace_bounds(bytes(table),128,grow.NEW)
        allowed=set()
        for number,name,start,sectors in grow.NEW:
            offset=(number-1)*128
            allowed.update(range(offset+32,offset+48))
            self.assertEqual(struct.unpack_from('<QQ',changed,offset+32),(start,start+sectors-1))
        self.assertTrue(all(a==b for index,(a,b) in enumerate(zip(table,changed)) if index not in allowed))
        sector=bytearray(random.Random(4).randbytes(512))
        header=grow.replace_header_crc(bytes(sector),changed)
        self.assertEqual(header[:16],sector[:16]);self.assertEqual(header[20:88],sector[20:88])
        self.assertEqual(header[92:],sector[92:])
        self.assertEqual(struct.unpack_from('<I',header,88)[0],zlib.crc32(changed))
        checked=bytearray(header[:92]);checked[16:20]=b'\0'*4
        self.assertEqual(struct.unpack_from('<I',header,16)[0],zlib.crc32(checked))


if __name__=='__main__':unittest.main()
