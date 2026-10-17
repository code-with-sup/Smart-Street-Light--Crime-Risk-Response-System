from pathlib import Path
from html import escape

out=Path(__file__).parent
s=['<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="2020" viewBox="0 0 2000 2020">','<rect width="2000" height="2020" fill="#f3f6fa"/>']
def box(x,y,w,h,fill='#fff',stroke='#ccd6e0',r=18):
    s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
def txt(x,y,t,n=24,c='#1d3048',b=400,a='start'):
    s.append(f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="{n}" fill="{c}" font-weight="{b}" text-anchor="{a}">{escape(t)}</text>')
def dot(x,y,c,r=8):
    s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" stroke="#283647" stroke-width="2"/>')
def wire(points,c,w=7):
    p=' '.join(f'{x},{y}' for x,y in points)
    for col,ww in [('#fff',w+5),(c,w)]:
        s.append(f'<polyline points="{p}" fill="none" stroke="{col}" stroke-width="{ww}" stroke-linejoin="round" stroke-linecap="round"/>')
def circle(x,y,r,c):
    s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>')
BROWN='#92532c'; BLUE='#1d6fd0'; YELLOW='#daa600'; RED='#ce3440'; GREEN='#198667'; BLACK='#263747'
txt(65,73,'LARGE MB-102: LED + BUZZER + PIR',48,b=700)
txt(65,122,'One breadboard, one ESP32. Use these pin names with your existing sketch.',29)
txt(65,166,'Unplug USB before wiring. Large coloured dots mark wire endpoints; crossing wires do not connect.',25,c='#94362d',b=700)
txt(65,208,'Colour is a guide: always check D2, D4, D5, VIN and GND printed on your board.',24)

# Large breadboard: upper 30 rows are enough; no lower rail section is used.
box(720,280,715,1265,'#f8f8f3','#a6b2b9',20)
txt(1077,320,'MB-102 • UPPER SECTION',28,b=700,a='middle')
xs={c:880+i*40 for i,c in enumerate('ABCDE')}
xs.update({c:1130+i*40 for i,c in enumerate('FGHIJ')})
def hole(c,r): return xs[c],400+(r-1)*33
for c,x in xs.items(): txt(x,365,c,23,b=700,a='middle')
box(1074,382,30,1010,'#dbe0e1','#dbe0e1',5)
for xx,col,label in [(752,'#d8a5a5','+'),(790,BLUE,'−'),(1357,BLUE,'−'),(1395,'#d8a5a5','+')]:
    s.append(f'<path d="M{xx} 380 V1384" stroke="{col}" stroke-width="3"/>')
    txt(xx,365,label,25,c=col,b=700,a='middle')
for r in range(1,31):
    yy=hole('A',r)[1]
    if r in [6,10,13,19,22]:
        col={6:'#ead6c7',10:'#ffdcda',13:'#fff0b6',19:'#d9eaff',22:'#fff0b6'}[r]
        box(862,yy-13,196,26,col,col,8)
    txt(831,yy+7,str(r),19,a='middle')
    txt(1320,yy+7,str(r),19,a='middle')
    for x in list(xs.values())+[752,790,1357,1395]:
        circle(x,yy,4.5,'#939da3')
txt(807,1432,'BLUE LEFT RAIL = COMMON GND',22,c=BLUE,b=700)
txt(757,1473,'Rows 31–63 below this section are unused.',22)
txt(757,1510,'Use one continuous rail section; bridge any rail break.',20)

# ESP32 abstract pin-name block, plus a physical header locator below.
box(75,300,405,775,'#243449','#182538')
box(230,265,95,70,'#c7d0d5','#82939c',7)
txt(277,375,'ESP32',42,c='#fff',b=700,a='middle')
txt(277,410,'PIN-NAME MAP',22,c='#bfcddd',a='middle')
ports={'D2':(480,450),'D4':(480,570),'GND':(480,690),'D5':(480,810),'VIN':(480,930)}
pc={'D2':BROWN,'D4':BLUE,'GND':YELLOW,'D5':GREEN,'VIN':RED}
for name,(x,y) in ports.items():
    txt(410,y+10,name,32,c='#fff',b=700,a='end')
    dot(x,y,pc[name],11)
txt(103,1010,'Wire to the printed pin names.',22,c='#fff')
txt(103,1042,'Actual pin positions shown below.',21,c='#cbd6e4')

# Signal wires and common ground. The white halo shows insulated crossings.
wire([ports['D2'],(640,450),(640,565),hole('A',6)],BROWN)
dot(*hole('A',6),BROWN)
txt(496,435,'BROWN • D2 → A6',21,c=BROWN,b=700)
wire([ports['D4'],(600,570),(600,994),hole('B',19)],BLUE)
dot(*hole('B',19),BLUE)
txt(610,965,'D4 → B19',21,c=BLUE,b=700)
wire([ports['GND'],(530,690),(530,1291),(790,1291)],YELLOW)
dot(790,1291,YELLOW)
txt(600,1258,'GND → blue rail',21,c='#8b6700',b=700)
wire([(790,796),hole('B',13)],YELLOW)
wire([(790,1093),hole('B',22)],YELLOW)
for p in [(790,796),hole('B',13),(790,1093),hole('B',22)]: dot(*p,YELLOW)

# Resistor: E6 to E10. Only its two ends are inserted.
e6=hole('E',6);e10=hole('E',10)
wire([e6,e10],'#7d8990',4)
box(e6[0]-13,596,26,69,'#dbc393','#88703f',4)
for yy,col in [(607,'#c13d38'),(620,'#c13d38'),(633,'#81502d'),(653,'#ad9137')]:
    s.append(f'<rect x="{e6[0]-13}" y="{yy}" width="26" height="6" fill="{col}"/>')
dot(*e6,'#7d8990');dot(*e10,'#7d8990')
box(1110,565,208,104,'#fff','#d5dfe6',8)
txt(1125,604,'330 Ω resistor',23,b=700)
txt(1125,637,'E6 ↔ E10',22)

# LED, with individually drawn long / short leads to different rows.
wire([(865,760),(865,697),hole('A',10)],RED,4)
wire([(895,760),(895,796),hole('A',13)],BLACK,4)
s.append('<path d="M859 751 V730 Q859 707 880 707 Q901 707 901 730 V751 Z" fill="#e64147" stroke="#9a2734" stroke-width="3"/>')
box(855,750,50,11,'#d83740','#9a2734',2)
txt(843,729,'+',25,c=RED,b=700,a='end')
txt(912,782,'−',25,c=BLACK,b=700)
dot(*hole('A',10),RED);dot(*hole('A',13),BLACK)
box(1110,681,208,126,'#fff','#d5dfe6',8)
txt(1125,720,'EXTERNAL LED',24,c=RED,b=700)
txt(1125,754,'Long leg (+) → A10',21)
txt(1125,787,'Short leg (−) → A13',21)

# Buzzer uses two rows of the same breadboard.
wire([(861,1050),(861,994),hole('A',19)],BLUE,4)
wire([(899,1050),(899,1093),hole('A',22)],BLACK,4)
circle(881,1031,34,'#27333e');circle(881,1031,5,'#d1bb86')
txt(857,1025,'+',19,c='#fff',b=700)
txt(898,1045,'−',19,c='#fff',b=700)
dot(*hole('A',19),BLUE);dot(*hole('A',22),BLACK)
box(1110,968,208,123,'#fff','#d5dfe6',8)
txt(1125,1005,'BUZZER',24,c=BLUE,b=700)
txt(1125,1038,'+ leg → A19',22)
txt(1125,1071,'− leg → A22',22)
box(844,1147,478,120,'#fff','#d5dfe6',8)
txt(852,1182,'A–E connect in each numbered row.',21)
txt(852,1213,'F–J form a separate group.',21)
txt(852,1244,'The centre trench separates them.',21)

# Three PIR connections, routed beneath the board and kept distinct.
wire([ports['D5'],(565,810),(565,1600),(1480,1600),(1480,835),(1680,835),(1680,805)],GREEN)
wire([ports['VIN'],(505,930),(505,1660),(1468,1660),(1468,815),(1535,815),(1535,805)],RED)
wire([(790,1357),(1457,1357),(1457,875),(1825,875),(1825,805)],BLACK)
dot(790,1357,BLACK)

box(1485,330,435,418,'#236c53','#164a39',15)
circle(1702,495,108,'#f0f2ef')
for x,y in [(1662,451),(1731,450),(1644,521),(1723,519),(1697,483)]:
    circle(x,y,24,'#e1e7e2')
box(1524,664,51,37,'#d2af46','#9a812c',4)
box(1830,664,51,37,'#d2af46','#9a812c',4)
txt(1702,725,'HC-SR501 PIR',28,c='#fff',b=700,a='middle')
for x,label,c in [(1535,'VCC',RED),(1680,'OUT',GREEN),(1825,'GND',BLACK)]:
    txt(x,785,label,24,c=c,b=700,a='middle');dot(x,805,c,10)
box(1500,952,440,323)
txt(1523,994,'PIR CONNECTIONS',27,b=700)
txt(1523,1037,'VCC → VIN / 5V (USB powered)',22,c=RED,b=700)
txt(1523,1080,'OUT → D5 / GPIO 5',23,c=GREEN,b=700)
txt(1523,1123,'GND → common GND rail',22,c=BLACK,b=700)
txt(1523,1172,'Match the labels on YOUR module.',21,b=700)
txt(1523,1207,'The pin order drawn is schematic.',21)
txt(1523,1242,'Allow about 60 s for PIR warm-up.',21)
txt(1510,1450,'Keep ESP32 and PIR beside',24,b=700)
txt(1510,1487,'the breadboard, as shown.',24,b=700)

# Photographed board pin locator, front side with USB at the top.
box(60,1360,430,615)
txt(80,1405,'ACTUAL ESP32 PIN LOCATOR',23,b=700)
txt(80,1438,'Front side • USB at TOP',22)
box(207,1480,147,435,'#263447','#182539',10)
box(248,1457,65,46,'#c9cfd3','#82919b',4)
box(228,1715,106,125,'#adbbbb','#87999b',4)
txt(280,1782,'ESP32',19,b=700,a='middle')
left=['3V3','GND','D15','D2','D4','RX2','TX2','D5','D18','D19','D21','RX0','TX0','D22','D23']
right=['VIN','GND','D13','D12','D14','D27','D26','D25','D33','D32','D35','D34','VN','VP','EN']
for i,(l,r) in enumerate(zip(left,right)):
    yy=1512+i*27
    lc=pc.get(l,'#63758a');rc=pc.get(r,'#63758a')
    dot(217,yy,lc,4);dot(344,yy,rc,4)
    txt(194,yy+6,l,20,c=lc,b=700 if l in pc else 400,a='end')
    txt(367,yy+6,r,20,c=rc,b=700 if r in pc else 400)
txt(80,1951,'Follow labels, not counted positions.',20,b=700)

box(550,1720,1390,255)
txt(580,1766,'CONNECT AND CHECK',29,b=700)
txt(580,1810,'1. Female jumper sockets go on ESP32 pins; male jumper ends go into breadboard holes.',24)
txt(580,1851,'2. Plug USB in, close Arduino Serial Monitor, then connect the USB port in Sensors & lights.',24)
txt(580,1892,'3. Press Full brightness. Then enable Buzzer and press Run test to check both outputs.',24)
txt(580,1940,'Keep the LED resistor in series. All grounds share the same blue rail section.',24,c='#94362d',b=700)
s.append('</svg>')
path=out/'esp32-mb102-all-connections.svg'
path.write_text('\n'.join(s))
print(path)
