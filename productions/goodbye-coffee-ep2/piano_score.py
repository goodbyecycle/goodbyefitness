# Original solo-piano score for Goodbye Coffee Ep. 2 (page-turn cut, 2:40).
# Additive-synthesis piano, 66 BPM, A minor -> C major. Writes audio/piano_dry.wav (mono, 48 kHz).
# Room reverb is added afterwards with ffmpeg:
#   ffmpeg -i audio/piano_dry.wav -af "aecho=0.8:0.75:47|91|163|277:0.32|0.24|0.16|0.1,lowpass=f=7000,highpass=f=40" piano.wav
import numpy as np, wave
SR=48000; TOTAL=160.0
L=60/66*4  # bar length ~3.636s
buf=np.zeros(int(SR*(TOTAL+6)))
def mf(m): return 440*2**((m-69)/12)
def note(t,m,vel,dur=2.5):
    f=mf(m); n=int(SR*(dur+3.0)); tt=np.arange(n)/SR
    B=0.0004; s=np.zeros(n)
    tau=2.2*(220/f)**0.45
    for k,a in enumerate([1,.55,.32,.2,.12,.08,.05],1):
        fk=k*f*np.sqrt(1+B*k*k)
        if fk>16000: break
        s+=a*np.sin(2*np.pi*fk*tt+np.random.rand()*0.3)*np.exp(-tt/(tau/(1+0.35*(k-1))))
    env=np.minimum(tt/0.004,1.0)
    rel=np.where(tt>dur, np.exp(-(tt-dur)/0.35),1.0)
    s*=env*rel*vel*(0.9 if m<48 else 1.0)
    i=int(t*SR); buf[i:i+n]+=s[:len(buf)-i]
C={'Am':[45,52,57,60,64],'F':[41,48,53,57,60],'C':[36,43,52,55,60],'G':[43,50,55,59,62],'Em':[40,47,52,55,59],'E':[40,47,52,56,59]}
def arp(bar,ch,vel,mel=None):
    t0=bar*L; c=C[ch]; b=L/4
    note(t0,c[0],vel*1.1,dur=L*0.95)
    for j,v in enumerate([c[2],c[3],c[4],c[3]]):
        note(t0+j*b+(0.01*j), v, vel*0.7, dur=b*1.6)
    if mel:
        for k,(off,m) in enumerate(mel): note(t0+off*b, m, vel*1.05, dur=b*2.2)
# Scene 1: sparse minor
for bar,(ch,hi) in enumerate([('Am',76),('F',72),('Am',71),('E',68)]):
    t0=bar*L; note(t0,C[ch][0],0.38,dur=L); note(t0+L*0.5,hi,0.22,dur=L*0.8)
# Walk + doctor lines: soft arpeggios
seq=['Am','F','C','G']*3
for i,ch in enumerate(seq[:11]): arp(4+i,ch,0.30)
# Bookstore: melody, warming
book=[('F',[(0,69),(2,72)]),('C',[(0,76),(2,74)]),('G',[(0,74),(2,71)]),('C',[(0,72),(1.5,76),(3,79)]),('C',[(0,79),(2,76)])]
for i,(ch,m) in enumerate(book): arp(15+i,ch,0.40,m)
# Cafe under narration
cafe=['C','G','Am','F']*4
for i,ch in enumerate(cafe[:15]):
    m=[(0,76),(2,74)] if i%4==0 and i>0 else None
    arp(20+i,ch,0.28,m)
# Choose wisely: hold and near-silence
note(35*L,41,0.30,dur=L*1.8); note(35*L,57,0.18,dur=L*1.8); note(35*L,60,0.16,dur=L*1.8)
note(36.5*L,72,0.16,dur=L)
# Final resolution
fin=[('Am',[(0,72),(2,76)]),('F',[(0,77),(2,76)]),('G',[(0,74),(2,71)]),('C',[(0,72),(2,79)])]
for i,(ch,m) in enumerate(fin): arp(37+i,ch,0.36,m)
t=41*L
for m_ in [36,43,48,52,55,60,64,72]: note(t,m_,0.30,dur=8.5)
buf=buf[:int(SR*TOTAL)]
fade=int(SR*5); buf[-fade:]*=np.linspace(1,0,fade)
buf/=np.max(np.abs(buf))*1.1
x=(buf*32767).astype(np.int16)
w=wave.open('audio/piano_dry.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes()); w.close()
print("ok", 41*L)
