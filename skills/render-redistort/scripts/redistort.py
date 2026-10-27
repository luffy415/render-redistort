"""Local STMap resampling: native image format/precision, lossless encoding, audited output."""
import argparse, hashlib, json, re, sys
from pathlib import Path
import numpy as np
import OpenImageIO as oiio
from scipy.ndimage import map_coordinates, spline_filter

SUPPORTED={'.exr','.png','.tif','.tiff'}
TYPES={'uint8':255.,'uint16':65535.,'half':None,'float':None,'double':None}

def require(ok,message):
    if not ok: raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def dump(path,data):
    Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def open_input(path):
    config=oiio.ImageSpec();config.attribute('oiio:UnassociatedAlpha',1)
    inp=oiio.ImageInput.open(str(path),config)
    require(inp is not None,f'Cannot open {path}: {oiio.geterror()}')
    return inp

def header(path,beauty=True):
    inp=open_input(path)
    try:
        s=oiio.ImageSpec(inp.spec())
        require(not s.deep,'Deep EXR requires a deep-aware host; flattening is forbidden.')
        require(not inp.seek_subimage(1,0),'Multipart/multipage input is unsupported; no parts will be discarded.')
        inp.seek_subimage(0,0)
        require(not inp.seek_subimage(0,1),'Mipmapped input is unsupported; no levels will be discarded.')
        require(s.depth==1 and s.x==s.y==s.z==s.full_x==s.full_y==0 and s.full_width==s.width and s.full_height==s.height,'Nonzero/cropped data or display window: expand in a verified host before mapping.')
        require(s.get_int_attribute('Orientation',1)==1,'Nontrivial orientation metadata is unsupported.')
        if beauty:
            require(Path(path).suffix.lower() in SUPPORTED,'Unsupported deliverable format; see formats-and-quality.md.')
            require(str(s.format) in TYPES,f'Unsupported native precision {s.format}')
            require(not s.channelformats or len(set(str(t) for t in s.channelformats))==1,'Mixed per-channel precision is unsupported.')
            require(tuple(s.channelnames) in [('R','G','B'),('R','G','B','A')],f'Only RGB/RGBA beauty supported, found {s.channelnames}; no AOVs will be dropped.')
            require(Path(path).suffix.lower()!='.exr' or str(s.format) in ('half','float'),'EXR beauty must be HALF or FLOAT.')
        return s
    finally:inp.close()

def read_pixels(path):
    inp=open_input(path)
    try:
        a=inp.read_image(oiio.DOUBLE)
        require(a is not None,f'Decode failed: {path}: {inp.geterror()}')
        require(np.isfinite(a).all(),f'Nonfinite pixel values in {path}')
        return a
    finally:inp.close()

def info(s):
    return dict(width=s.width,height=s.height,channels=list(s.channelnames),native_type=str(s.format),channel_types=[str(x) for x in s.channelformats],compression=s.get_string_attribute('compression'),colorspace=s.get_string_attribute('oiio:ColorSpace'),alpha_channel=s.alpha_channel)

def frames(path):
    path=Path(path);require(path.exists(),f'Missing input: {path}')
    if path.is_file():return [(None,path)]
    files=sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
    require(files,'No supported frames. Videos require the format routing in the skill.')
    seq=[];families=set()
    for p in files:
        m=re.fullmatch(r'(.*?)(\d+)(\.[^.]+)',p.name)
        require(m is not None,f'Numbered sequence required: {p.name}')
        families.add((m[1],m[3].lower(),len(m[2])));seq.append((int(m[2]),p))
    require(len(families)==1,'Ambiguous directory: multiple prefixes, formats or padding.')
    seq.sort();numbers=[f[0] for f in seq]
    require(len(set(numbers))==len(numbers),'Duplicate frame identifiers.')
    require(numbers==list(range(numbers[0],numbers[-1]+1)),'Missing frames; retiming/interpolation is forbidden.')
    return seq

def resolve_job(path):
    path=Path(path).resolve();j=json.loads(path.read_text(encoding='utf-8-sig'))
    require(j.get('version')==1,'Expected job version 1.')
    for key in ('input','map','output'):
        p=Path(j[key]);j[key]=str((path.parent/p).resolve() if not p.is_absolute() else p.resolve())
    m=j['mapping'];im=j['image']
    require(m.get('direction')=='output_to_input','Explicit output-to-input sampling required.')
    require(m.get('space') in ('stmap_uv','pixel_xy'),'Map space must be stmap_uv or pixel_xy.')
    for key in ('source_size','output_size'):
        require(key in m and len(m[key])==2 and all(type(v) is int and v>1 for v in m[key]),f'Declare valid {key}; dimensions will not be guessed.')
    if m['space']=='stmap_uv':
        require(m.get('uv_origin') in ('bottom_left','top_left'),'Explicit UV origin required.')
        require(m.get('normalization')=='pixel_edges','Only pixel-edge normalization: center=(pixel+0.5)/size.')
    require(im.get('color_space') in ('linear','srgb'),'Declare linear or srgb. Log/unknown needs an explicit OCIO host workflow.')
    require(im.get('alpha') in ('none','straight','premultiplied'),'Declare alpha association.')
    require(not (im['color_space']=='srgb' and im['alpha']=='premultiplied'),'sRGB-premultiplied input is ambiguous; use a verified linear workflow.')
    require(im.get('filter','cubic') in ('cubic','linear'),'Supported filters: cubic or linear.')
    require(im.get('border','error') in ('error','black'),'Supported borders: error or explicitly requested black.')
    require(not Path(j['output']).exists(),'Output already exists; choose a fresh output directory.')
    return j

def prepare(j):
    source=frames(j['input']);mp=Path(j['map']);m=j['mapping']
    if mp.is_dir():
        maps=dict(frames(mp));require(source[0][0] is not None,'Animated maps need numbered renders.')
        offset=m.get('map_frame_offset',0);require(type(offset) is int,'map_frame_offset must be integer.')
        require(set(maps)=={n+offset for n,_ in source},'Map/render frame identifiers differ; declare offset and provide exactly matching ranges.')
        selected=[(n,p,maps[n+offset]) for n,p in source]
    else:
        require(mp.is_file(),f'Map missing: {mp}');selected=[(n,p,mp) for n,p in source]
    first=None
    for _,p,_ in selected:
        s=header(p);require([s.width,s.height]==m['source_size'],f'Render size mismatch: {p.name}')
        signature=(s.width,s.height,s.nchannels,str(s.format),tuple(s.channelnames),p.suffix.lower())
        if first is None:first=signature
        require(signature==first,'Sequence format/precision/channels change between frames.')
        require((s.nchannels==4)==(j['image']['alpha']!='none'),'Alpha declaration does not match source channels.')
        if p.suffix.lower()=='.png':require(j['image']['alpha'] in ('straight','none'),'PNG requires straight alpha.')
    return selected

def load_map(path,m,border):
    sw,sh=m['source_size'];ow,oh=m['output_size']
    if Path(path).suffix.lower()=='.npy':
        require(m['space']=='pixel_xy','NPY maps use top-left integer-center pixel_xy.')
        a=np.load(path,allow_pickle=False)
        require(a.dtype in (np.float32,np.float64) and a.shape==(oh,ow,2),'NPY must be float H×W×2.')
        x=np.array(a[:,:,0],dtype=np.float64);y=np.array(a[:,:,1],dtype=np.float64)
    else:
        s=header(path,beauty=False);require([s.width,s.height]==[ow,oh],'Map size differs from output raster.')
        require(str(s.format) in ('float','double'),'Map must be 32-bit float or higher non-color data; HALF/integer maps rejected.')
        names=m.get('channels',['R','G']);require(len(names)==2 and names[0]!=names[1],'Two distinct map channels required.')
        require(all(n in s.channelnames for n in names),'Map channels missing.')
        channel_types=list(s.channelformats) or [s.format]*s.nchannels
        require(all(str(channel_types[list(s.channelnames).index(n)]) in ('float','double') for n in names),'Each selected map channel must be 32-bit float or higher; mixed HALF UV channels are rejected.')
        a=read_pixels(path);x=a[:,:,list(s.channelnames).index(names[0])].copy();y=a[:,:,list(s.channelnames).index(names[1])].copy()
        if m['space']=='stmap_uv':
            x=x*sw-.5;y=(1-y)*sh-.5 if m['uv_origin']=='bottom_left' else y*sh-.5
    require(np.isfinite(x).all() and np.isfinite(y).all(),'Nonfinite map coordinates.')
    tolerance=float(max(sw,sh)*np.finfo(np.float32).eps)
    valid=(x>=-tolerance)&(x<=sw-1+tolerance)&(y>=-tolerance)&(y<=sh-1+tolerance)
    outside=int((~valid).sum())
    require(not outside or border=='black',f'{outside} pixels lack source coverage. Supply matching overscan or explicitly authorize black borders.')
    x=np.clip(x,0,sw-1);y=np.clip(y,0,sh-1)
    return x,y,valid,dict(output_size=[ow,oh],source_size=[sw,sh],outside_source_pixels=outside,border=border,boundary_roundoff_tolerance_px=tolerance)

def srgb_decode(a):
    return np.where(a<=.04045,a/12.92,((np.maximum(a,0)+.055)/1.055)**2.4)

def srgb_encode(a):
    return np.where(a<=.0031308,12.92*a,1.055*np.maximum(a,0)**(1/2.4)-.055)

def warp(pixels,x,y,valid,settings):
    a=pixels.copy();alpha=settings['alpha'];srgb=settings['color_space']=='srgb'
    require(alpha=='none' or (a[:,:,3].min()>=0 and a[:,:,3].max()<=1),'Source alpha outside [0,1].')
    if srgb:a[:,:,:3]=srgb_decode(a[:,:,:3])
    if alpha=='straight':a[:,:,:3]*=a[:,:,3:4]
    order=3 if settings.get('filter','cubic')=='cubic' else 1
    result=np.empty((*x.shape,a.shape[2]),np.float64)
    for c in range(a.shape[2]):
        channel=spline_filter(a[:,:,c],order=3,mode='nearest') if order==3 else a[:,:,c]
        for y0 in range(0,len(x),128):
            result[y0:y0+128,:,c]=map_coordinates(channel,[y[y0:y0+128],x[y0:y0+128]],order=order,mode='nearest',prefilter=False)
    clipped_alpha=0
    if alpha!='none':
        old=result[:,:,3].copy();clipped_alpha=int(((old<0)|(old>1)).sum());result[:,:,3]=np.clip(old,0,1)
        if alpha=='straight':
            np.divide(result[:,:,:3],result[:,:,3:4],out=result[:,:,:3],where=result[:,:,3:4]>1e-12)
            result[:,:,:3][result[:,:,3]<=1e-12]=0
    if srgb:result[:,:,:3]=srgb_encode(result[:,:,:3])
    result[~valid]=0;require(np.isfinite(result).all(),'Resampling produced nonfinite values.')
    return result,dict(alpha_range_clamped_pixels=clipped_alpha,filter='cubic B-spline (prefiltered)' if order==3 else 'bilinear',working_precision='float64')

def write_and_verify(path,source_spec,pixels,settings):
    s=oiio.ImageSpec(source_spec);h,w=pixels.shape[:2]
    s.width=s.full_width=w;s.height=s.full_height=h
    s.x=s.y=s.z=s.full_x=s.full_y=s.full_z=0;s.tile_width=s.tile_height=s.tile_depth=0
    s.attribute('compression','zip');s.attribute('oiio:dither',0)
    s.attribute('oiio:UnassociatedAlpha',1 if settings['alpha']=='straight' else 0)
    for name in ('tiff:Compression','tiff:RowsPerStrip','Exif:PixelXDimension','Exif:PixelYDimension'):s.erase_attribute(name)
    native=str(source_spec.format);maximum=TYPES[native];work=pixels.copy();clipped=0
    if maximum:
        clipped=int(((work<0)|(work>1)).sum());work=np.clip(work,0,1)
        encoded=np.floor(work*maximum+.5).astype(np.uint8 if native=='uint8' else np.uint16)
        target=encoded.astype(np.float64)/maximum;tolerance=1e-7
    else:
        with np.errstate(over='ignore'):encoded=work.astype({'half':np.float16,'float':np.float32,'double':np.float64}[native])
        require(np.isfinite(encoded).all(),'Values exceed native float range; precision will not be silently changed.')
        target=encoded.astype(np.float64);tolerance=0.
    out=oiio.ImageOutput.create(str(path));require(out is not None,oiio.geterror())
    require(out.open(str(path),s),f'Cannot create {path}: {out.geterror()}')
    try:require(out.write_image(encoded),f'Write failed: {out.geterror()}')
    finally:require(out.close(),f'Close failed: {out.geterror()}')
    saved=header(path);decoded=read_pixels(path)
    require(str(saved.format)==native and tuple(saved.channelnames)==tuple(source_spec.channelnames),'Saved precision/channels changed.')
    require(decoded.shape==target.shape,'Saved raster size changed.')
    error=float(np.max(abs(decoded-target)));require(error<=tolerance,f'Saved pixels differ: {error} > {tolerance}')
    preserved=[]
    for name in ('oiio:ColorSpace','chromaticities','ICCProfile','smpte:TimeCode'):
        old=source_spec.getattribute(name)
        if old is not None:
            require(str(old)==str(saved.getattribute(name)),f'Color/timing metadata changed: {name}');preserved.append(name)
    return dict(saved=info(saved),decode_max_abs_error=error,integer_range_clipped_samples=clipped,preserved_critical_metadata=preserved,compression_policy='lossless ZIP/Deflate; same file format/native precision')

def run(job_path,check_only=False):
    j=resolve_job(job_path);selection=prepare(j);im=j['image'];m=j['mapping']
    hashes={str(p):sha(p) for _,_,p in selection}
    for mp in hashes:load_map(mp,m,im.get('border','error'))
    if check_only:return dict(status='preflight_passed',frames=len(selection),job=j,map_count=len(hashes))
    out=Path(j['output']);out.mkdir(parents=True,exist_ok=False)
    manifest=dict(schema='render_redistort_manifest_v1',status='running',job=j,software=dict(python=sys.version.split()[0],numpy=np.__version__,openimageio=oiio.VERSION_STRING),map_sha256=hashes,frames=[],quality='One required spatial resampling; no additional lossy encoding or bit-depth reduction. Not mathematically lossless.',timing=j.get('timing',{}))
    mp_out=out/'redistort_manifest.json';dump(mp_out,manifest);cached=None;cached_map=None
    try:
        for index,p,mp in selection:
            source_hash=sha(p);s=header(p)
            if cached!=str(mp):cached_map=load_map(mp,m,im.get('border','error'));cached=str(mp)
            x,y,valid,map_info=cached_map;image=read_pixels(p)
            identity=image.shape[:2]==x.shape and np.array_equal(x,np.broadcast_to(np.arange(s.width),x.shape)) and np.array_equal(y,np.broadcast_to(np.arange(s.height)[:,None],y.shape)) and valid.all()
            if identity:result=image;warp_info=dict(identity_map=True,filter='identity / no resampling',working_precision='float64',alpha_range_clamped_pixels=0)
            else:result,warp_info=warp(image,x,y,valid,im)
            destination=out/p.name;verification=write_and_verify(destination,s,result,im)
            require(sha(p)==source_hash,f'Source changed during processing: {p}')
            require(sha(mp)==hashes[str(mp)],f'Map changed during processing: {mp}')
            manifest['frames'].append(dict(frame=index,input=str(p),input_sha256=source_hash,output=destination.name,output_sha256=sha(destination),source=info(s),map=map_info,resampling=warp_info,verification=verification))
            dump(mp_out,manifest);print(json.dumps(dict(completed=len(manifest['frames']),total=len(selection),file=destination.name)),flush=True)
        manifest['status']='complete';manifest['frame_count']=len(selection);dump(mp_out,manifest);return manifest
    except Exception as exc:
        manifest['status']='failed';manifest['error']=str(exc);dump(mp_out,manifest);raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('inspect');p.add_argument('input')
    p=sub.add_parser('run');p.add_argument('job');p.add_argument('--check-only',action='store_true')
    a=parser.parse_args()
    try:
        if a.command=='inspect':
            fs=frames(a.input);result=dict(frame_count=len(fs),frame_range=[fs[0][0],fs[-1][0]],images=[dict(path=str(p),frame=n,**info(header(p))) for n,p in fs])
        else:
            result=run(a.job,a.check_only)
            if not a.check_only:result={k:result[k] for k in ('status','frame_count','quality')}
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except Exception as exc:
        print(json.dumps(dict(status='error',error=str(exc)),ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
