"""Caption real Playwright footage and hold its asserted screenshots for reading.

No chart pixels or values are redrawn. Validation compares encoded result frames
with their original checkpoint screenshots; contact sheets support visual review.
"""
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat
import imageio_ffmpeg

RUN = Path(sys.argv[1]).resolve()
OUT = RUN / 'films'
OUT.mkdir(exist_ok=True)
FFMPEG = os.environ.get('CSIM_FFMPEG') or imageio_ffmpeg.get_ffmpeg_exe()
WIDTH, CONTENT, HEIGHT, FPS = 1440, 1000, 1080, 24
FONT_PATHS = [os.environ.get('CSIM_VIDEO_FONT',''), '/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
FONT = next((p for p in FONT_PATHS if p and Path(p).is_file()), None)
if not FONT:
    raise SystemExit('Set CSIM_VIDEO_FONT to a readable TrueType font')


def font(size):
    return ImageFont.truetype(FONT, size)


def lines(draw, text, size, width):
    result, row = [], ''
    for word in text.split():
        candidate=(row+' '+word).strip()
        if row and draw.textlength(candidate,font=font(size)) > width:
            result.append(row); row=word
        else:
            row=candidate
    return result+[row]


def draw_text(draw, text, xy, size, fill, width, gap=12):
    x,y=xy
    for row in lines(draw,text,size,width):
        draw.text((x,y),row,font=font(size),fill=fill)
        y+=size+gap
    return y


def card(path, title, body, eyebrow='CSiM / Dashboard workflows'):
    im=Image.new('RGB',(WIDTH,HEIGHT),'#f5f6f3');d=ImageDraw.Draw(im)
    d.rectangle((92,178,1348,185),fill='#24665f')
    d.text((94,224),eyebrow,font=font(26),fill='#24665f')
    y=draw_text(d,title,(90,305),56,'#24383c',1240,16)+38
    draw_text(d,body,(94,y),32,'#53686c',1220,17)
    d.text((94,HEIGHT-70),'CSiM dashboard issues and solutions',font=font(22),fill='#53686c')
    im.save(path)


def checkpoint(source, banner_path, path):
    im=Image.new('RGB',(WIDTH,HEIGHT),'#e8ece8')
    shot=Image.open(source).convert('RGB')
    shot.thumbnail((WIDTH,CONTENT))
    # Keep the complete screenshot, including native filter controls and axes.
    im.paste(shot,((WIDTH-shot.width)//2,0))
    im.paste(Image.open(banner_path).convert('RGB'),(0,CONTENT))
    im.save(path)


def banner(path, chapter, caption):
    im=Image.new('RGB',(WIDTH,HEIGHT-CONTENT),'#203936');d=ImageDraw.Draw(im)
    text=chapter+' · '+caption
    wrapped=lines(d,text,22,1392)
    if len(wrapped)>2: raise ValueError('Caption needs shortening: '+caption)
    draw_text(d,text,(24,12),22,'white',1392,8)
    im.save(path)


def encode(args, destination):
    cmd=[FFMPEG,'-hide_banner','-loglevel','error','-y',*args,'-an','-r',str(FPS),'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-threads','2',str(destination)]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)


def still(image, seconds, dest):
    encode(['-loop','1','-i',str(image),'-t',str(seconds)], dest)


def duration(video):
    r=subprocess.run([FFMPEG,'-hide_banner','-i',str(video)],capture_output=True,text=True)
    match=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',r.stderr)
    if not match: raise ValueError('Cannot read duration: '+str(video))
    h,m,s=map(float,match.groups()); return 3600*h+60*m+s


def timestamp(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02}.{ms:03}'


def decode_attachment(a):
    if a.get('body'):
        import base64
        return json.loads(base64.b64decode(a['body']))
    return json.loads(Path(a['path']).read_text())


def make_film(item):
    number=item['title'][:2];work=OUT/number;work.mkdir(exist_ok=True)
    data=item['tests'][0]['results'][-1]
    if data['status']!='passed': raise ValueError('Only passing footage can become a demonstration')
    attachments=data.get('attachments',[])
    raw=Path(next(a['path'] for a in attachments if a['contentType']=='video/webm'))
    timeline=decode_attachment(next(a for a in attachments if a['name']=='video-scenes'))
    assets={a['name']:a for a in attachments if a['contentType']=='image/png'}
    guide=GUIDE[number]
    parts=[];captions=[];checks=[];position=0.0;last=0.0;last_chapter=None
    def add_still(path,seconds,caption):
        nonlocal position
        seconds=math.ceil(seconds*FPS)/FPS
        dest=work/f'part-{len(parts):03}.mp4';still(path,seconds,dest);parts.append(dest)
        captions.append((position,position+seconds,caption));position+=seconds
    intro_text=guide.get('videoIntro',guide['try'])
    intro=work/'intro.png';card(intro,guide['label'],intro_text)
    add_still(intro,max(5,len(intro_text.split())/2.5),guide['label']+'. '+intro_text)
    intro_check={'time':2,'source':str(intro),'label':'Introduction'}
    checks.append(intro_check)
    raw_duration=duration(raw)
    for index,scene in enumerate(timeline['scenes']):
        end=min(raw_duration,max(last,scene['atSeconds']))
        if not scene.get('publish',True):
            last=end
            continue
        chapter=scene['chapter'];caption=scene['caption']
        major=scene.get('majorBreak')
        if major and major!=last_chapter:
            chapter_card=work/f'chapter-{index}.png';card(chapter_card,major,'','CSiM / '+guide['label'])
            before=position
            add_still(chapter_card,4,major)
            checks.append({'time':before+1.5,'source':str(chapter_card),'label':major})
            last_chapter=major
        strip=work/f'caption-{index}.png';banner(strip,chapter,caption)
        clip_seconds=math.floor((end-last)*FPS)/FPS
        if clip_seconds>=0.25:
            clip=work/f'part-{len(parts):03}.mp4'
            encode(['-ss',str(last),'-i',str(raw),'-loop','1','-i',str(strip),'-t',str(clip_seconds),
                '-filter_complex',f'[0:v]scale={WIDTH}:{CONTENT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:0:color=0xe8ece8[screen];[screen][1:v]overlay=0:{CONTENT}:shortest=1'],clip)
            parts.append(clip);captions.append((position,position+clip_seconds,caption));position+=clip_seconds
        last=end
        attachment=assets[scene['name']]
        if attachment.get('path'): source=Path(attachment['path'])
        else:
            import base64
            source=work/f'source-{index}.png';source.write_bytes(base64.b64decode(attachment['body']))
        held=work/f'checkpoint-{index}.png';checkpoint(source,strip,held)
        before=position;hold=max(6,len(caption.split())/2.5)
        add_still(held,hold,caption)
        checks.append({'time':before+hold/2,'source':str(held),'label':scene['name'],'assertedScreenshot':str(source),'holdSeconds':hold})
    outro=guide.get('videoOutro',guide['expected'])
    end_card=work/'result.png';card(end_card,'What remains' if number in ['03','08','09'] else 'Result',outro)
    end_before=position;add_still(end_card,max(6,len(outro.split())/2.5),outro)
    checks.append({'time':end_before+2,'source':str(end_card),'label':'Result'})
    listing=work/'parts.txt';listing.write_text(''.join("file '"+str(p).replace("'","'\\''")+"'\n" for p in parts))
    movie=OUT/f'workflow-{number}.mp4'
    subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(movie)],check=True,stderr=subprocess.PIPE)
    # Keep an unchanged caption continuous across an interaction and its hold.
    continuous=[]
    for a,b,text in captions:
        if continuous and continuous[-1][2]==text and abs(continuous[-1][1]-a)<0.001:
            continuous[-1]=(continuous[-1][0],b,text)
        else: continuous.append((a,b,text))
    vtt=OUT/f'workflow-{number}.vtt';vtt.write_text('WEBVTT\n\n'+''.join(f'{timestamp(a)} --> {timestamp(b)}\n{text}\n\n' for a,b,text in continuous))
    # Check frames from the encoded final file, including every held result.
    for index,check in enumerate(checks):
        frame=work/f'encoded-{index:02}.png'
        subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-ss',str(check['time']),'-i',str(movie),'-frames:v','1',str(frame)],check=True,stderr=subprocess.PIPE)
        expected=Image.open(check['source']).convert('RGB');actual=Image.open(frame).convert('RGB')
        if actual.size!=expected.size: raise AssertionError('Encoded frame dimensions changed')
        # Compare the actual encoded frame, rather than a renderer-side image.
        diff=ImageStat.Stat(ImageChops.difference(expected,actual)).mean
        check['meanPixelDifference']=round(sum(diff)/3,3);check['frame']=str(frame)
        if check['meanPixelDifference']>6: raise AssertionError(f'Video does not match checkpoint: {number} {check}')
    # Contact sheets expose intro, chapter, result and every asserted checkpoint.
    sheets=[]
    for offset in range(0,len(checks),9):
        batch=checks[offset:offset+9];sheet=Image.new('RGB',(1440,1275),'white');d=ImageDraw.Draw(sheet)
        for j,check in enumerate(batch):
            frame=Image.open(check['frame']);frame.thumbnail((480,390));x=(j%3)*480;y=(j//3)*425
            sheet.paste(frame,(x,y+30));d.text((x+6,y+4),check['label'][:62],font=font(13),fill='#24383c')
        name=OUT/f'workflow-{number}-frames-{offset//9+1}.jpg';sheet.save(name,quality=88);sheets.append(str(name))
    result={'title':item['title'],'file':str(movie),'captions':str(vtt),'durationSeconds':duration(movie),'scenes':sum(s.get('publish',True) for s in timeline['scenes']),'framesChecked':len(checks),'maxPixelDifference':max(c['meanPixelDifference'] for c in checks),'contactSheets':sheets,'checkpoints':checks}
    (work/'validation.json').write_text(json.dumps(result,indent=2))
    print(f'{number}: {len(checks)} encoded frames match; {result["durationSeconds"]:.1f}s',flush=True)
    return number,result

report=json.loads((RUN/'results.json').read_text())
provenance=json.loads((RUN/'provenance.json').read_text())
# Use the caption guide captured with this run, not a later edited source file.
GUIDE=json.loads((RUN/'workflow-guide.json').read_text())
specs=[]
def collect(s):
    specs.extend(s.get('specs',[]))
    for child in s.get('suites',[]):collect(child)
collect(report)
policy=json.loads((RUN/'publication.json').read_text())
specs=[spec for spec in specs if spec['title'][:2] in policy['workflowIds']]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=dict(pool.map(make_film,specs))
(OUT/'manifest.json').write_text(json.dumps({'format':1,'run':provenance['timestamp'],'rendererSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'encoder':subprocess.check_output([FFMPEG,'-version'],text=True).splitlines()[0],'workflows':results},indent=2))
print(f'Captioned {len(results)} workflows with verified encoded frames.')
