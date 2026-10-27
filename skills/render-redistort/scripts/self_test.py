"""Synthetic forward tests; no production footage or network. Exit nonzero on failure."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
import OpenImageIO as o
import redistort as r

class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='render-redistort-test-');self.root=Path(self.tmp.name)
        self.h,self.w=32,64
        yy,xx=np.mgrid[:self.h,:self.w];self.xy=np.stack([xx,yy],-1).astype(np.float32)
        np.save(self.root/'map.npy',self.xy)
    def tearDown(self):self.tmp.cleanup()
    def write(self,name,a,typ,attributes=None):
        p=self.root/name;s=o.ImageSpec(a.shape[1],a.shape[0],a.shape[2],typ)
        s.attribute('compression','zip');s.attribute('oiio:UnassociatedAlpha',1)
        for k,v in (attributes or {}).items():s.attribute(k,v)
        out=o.ImageOutput.create(str(p));self.assertTrue(out.open(str(p),s));self.assertTrue(out.write_image(a));self.assertTrue(out.close());return p
    def job(self,source,alpha='none',space='linear',mapping=None,suffix='out'):
        j=dict(version=1,input=str(source),map=str(self.root/'map.npy'),output=str(self.root/suffix),mapping=dict(space='pixel_xy',direction='output_to_input',source_size=[self.w,self.h],output_size=[self.w,self.h]),image=dict(color_space=space,alpha=alpha,filter='cubic',border='error'),timing=dict(fps_numerator=24000,fps_denominator=1001))
        if mapping:j['mapping'].update(mapping)
        p=self.root/(suffix+'.json');r.dump(p,j);return p
    def test_01_native_precision_identity(self):
        rng=np.random.default_rng(23)
        cases=[('u8.png',o.UINT8,np.uint8,255),('u16.png',o.UINT16,np.uint16,65535),('u16.tif',o.UINT16,np.uint16,65535),('hdr16.exr',o.HALF,np.float16,None),('hdr32.exr',o.FLOAT,np.float32,None),('hdr32.tif',o.FLOAT,np.float32,None)]
        for i,(name,typ,dtype,maximum) in enumerate(cases):
            with self.subTest(name=name):
                a=(rng.integers(0,maximum+1,(self.h,self.w,3),dtype=dtype) if maximum else rng.uniform(-.25,25,(self.h,self.w,3)).astype(dtype))
                src=self.write(name,a,typ);before=r.sha(src)
                result=r.run(self.job(src,suffix='out'+str(i)))
                self.assertEqual(result['status'],'complete');self.assertEqual(before,r.sha(src))
                self.assertTrue(np.array_equal(r.read_pixels(src),r.read_pixels(self.root/('out'+str(i))/name)))
                self.assertEqual(str(r.header(src).format),str(r.header(self.root/('out'+str(i))/name).format))
    def test_02_uv_origin_and_asymmetric_shift(self):
        yy,xx=np.mgrid[:self.h,:self.w]
        a=np.stack([xx,yy,3*xx+7*yy],-1).astype(np.float32)
        src=self.write('ramp.exr',a,o.FLOAT)
        sx=np.clip(xx+2,0,self.w-1);sy=np.clip(yy+1,0,self.h-1)
        uv=np.stack([(sx+.5)/self.w,1-(sy+.5)/self.h,np.zeros_like(xx)],-1).astype(np.float32)
        mp=self.write('uv.exr',uv,o.FLOAT)
        p=self.job(src,mapping=dict(space='stmap_uv',uv_origin='bottom_left',normalization='pixel_edges',channels=['R','G']))
        j=json.loads(p.read_text());j['map']=str(mp);r.dump(p,j)
        r.run(p);saved=r.read_pixels(self.root/'out/ramp.exr')
        self.assertLess(np.max(abs(saved-a[sy,sx])),1e-4)
    def test_03_straight_alpha_no_hidden_color_bleed(self):
        a=np.zeros((self.h,self.w,4),np.float32);a[:,:32,0]=1;a[:,:32,3]=1;a[:,32:,2]=100
        src=self.write('rgba.exr',a,o.FLOAT)
        xy=self.xy.copy();xy[:,:,0]=np.clip(xy[:,:,0]+.5,0,self.w-1);np.save(self.root/'map.npy',xy)
        r.run(self.job(src,alpha='straight'));out=r.read_pixels(self.root/'out/rgba.exr')
        self.assertLess(abs(out[:,:,2]).max(),1e-8)
        self.assertGreater(out[16,31,3],.1);self.assertLess(out[16,31,3],.9)
    def test_04_linear_light_srgb(self):
        a=np.zeros((self.h,self.w,3),np.uint16);a[:,32:]=65535
        src=self.write('contrast.png',a,o.UINT16)
        xy=self.xy.copy();xy[:,:,0]=np.clip(xy[:,:,0]+.5,0,self.w-1);np.save(self.root/'map.npy',xy)
        p=self.job(src,space='srgb');j=json.loads(p.read_text());j['image']['filter']='linear';r.dump(p,j)
        r.run(p);out=r.read_pixels(self.root/'out/contrast.png')
        self.assertAlmostEqual(float(out[16,31,0]),.73535698,places=4)
    def test_05_refuse_bad_coverage_and_overwrite(self):
        src=self.write('rgb.exr',np.ones((self.h,self.w,3),np.float32),o.FLOAT)
        p=self.job(src);xy=self.xy.copy();xy[0,0,0]=-20;np.save(self.root/'map.npy',xy)
        with self.assertRaisesRegex(ValueError,'coverage'):r.run(p)
        self.assertFalse((self.root/'out').exists())
        np.save(self.root/'map.npy',self.xy);r.run(p)
        with self.assertRaisesRegex(ValueError,'already exists'):r.run(p)
    def test_06_sequence_gaps_and_precision_changes(self):
        seq=self.root/'seq';seq.mkdir()
        for name in ['f.0001.png','f.0003.png']:
            self.write('seq/'+name,np.zeros((self.h,self.w,3),np.uint16),o.UINT16)
        with self.assertRaisesRegex(ValueError,'Missing frames'):r.run(self.job(seq),True)
    def test_07_native_alpha_png_and_color_metadata(self):
        rng=np.random.default_rng(5);a=rng.integers(0,65536,(self.h,self.w,4),dtype=np.uint16)
        src=self.write('alpha.png',a,o.UINT16)
        r.run(self.job(src,alpha='straight',space='srgb'))
        self.assertTrue(np.array_equal(r.read_pixels(src),r.read_pixels(self.root/'out/alpha.png')))
    def test_08_reject_half_precision_map(self):
        src=self.write('rgb.exr',np.zeros((self.h,self.w,3),np.float32),o.FLOAT)
        uv=np.zeros((self.h,self.w,3),np.float16);mp=self.write('badmap.exr',uv,o.HALF)
        p=self.job(src,mapping=dict(space='stmap_uv',uv_origin='bottom_left',normalization='pixel_edges'))
        j=json.loads(p.read_text());j['map']=str(mp);r.dump(p,j)
        with self.assertRaisesRegex(ValueError,'32-bit'):r.run(p)
    def test_09_animated_map_frame_binding(self):
        seq=self.root/'seq';seq.mkdir();maps=self.root/'maps';maps.mkdir()
        for idx in [10,11]:
            self.write(f'seq/f.{idx:04d}.exr',np.ones((self.h,self.w,3),np.float32)*idx,o.FLOAT)
            uv=np.stack([(self.xy[:,:,0]+.5)/self.w,1-(self.xy[:,:,1]+.5)/self.h,np.zeros((self.h,self.w))],-1).astype(np.float32)
            self.write(f'maps/m.{idx-10:04d}.exr',uv,o.FLOAT)
        p=self.job(seq,mapping=dict(space='stmap_uv',uv_origin='bottom_left',normalization='pixel_edges',map_frame_offset=-10))
        j=json.loads(p.read_text());j['map']=str(maps);r.dump(p,j);result=r.run(p)
        self.assertEqual([f['frame'] for f in result['frames']],[10,11])
    def test_10_reject_half_uv_in_mixed_exr(self):
        src=self.write('rgb.exr',np.zeros((self.h,self.w,3),np.float32),o.FLOAT)
        mp=self.root/'mixed.exr';s=o.ImageSpec(self.w,self.h,3,o.FLOAT)
        s.channelformats=[o.TypeDesc('half'),o.TypeDesc('half'),o.TypeDesc('float')]
        out=o.ImageOutput.create(str(mp));self.assertTrue(out.open(str(mp),s));self.assertTrue(out.write_image(np.zeros((self.h,self.w,3),np.float32)));out.close()
        p=self.job(src,mapping=dict(space='stmap_uv',uv_origin='bottom_left',normalization='pixel_edges'))
        j=json.loads(p.read_text());j['map']=str(mp);r.dump(p,j)
        with self.assertRaisesRegex(ValueError,'32-bit'):r.run(p,True)

if __name__=='__main__':unittest.main(verbosity=2)
