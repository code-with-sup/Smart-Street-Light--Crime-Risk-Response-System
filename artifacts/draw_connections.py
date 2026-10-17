from pathlib import Path
from html import escape

out = Path(__file__).parent
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="2050" viewBox="0 0 1600 2050">', '<rect width="1600" height="2050" fill="#f3f6fa"/>']
def rect(x,y,w,h,fill='#ffffff',stroke='#cad5e2',r=20):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
def text(x,y,s,size=24,color='#182b42',weight=400,anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(s)}</text>')
def line(points,color,width=7):
    parts.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
def circle(x,y,r,fill,stroke='none',sw=2):
    parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def dot(x,y,color):
    circle(x,y,10,color,'#182b42')
def breadboard(x,y,rows,spacing=50):
    h=(len(rows)-1)*spacing+110
    rect(x,y,460,h,'#eef0ed','#a7b4bd',12)
    text(x+230,y+26,'BREADBOARD • A–E HALF',19,weight=700,anchor='middle')
    for i,c in enumerate('ABCDE'):
        text(x+90+i*65,y+53,c,22,weight=700,anchor='middle')
    for ri,row in enumerate(rows):
        yy=y+85+ri*spacing
        shades={6:'#ecd1bf',10:'#ffcfcf',13:'#fff0a6',19:'#d0e5ff',22:'#fff0a6'}
        if row in shades:
            rect(x+70,yy-18,300,36,shades[row],shades[row],10)
        text(x+40,yy+7,str(row),20,anchor='middle')
        text(x+410,yy+7,str(row),20,anchor='middle')
        for ci in range(5):
            circle(x+90+ci*65,yy,7,'#8d969a','#ffffff')
    return lambda col,row: (x+90+'ABCDE'.index(col)*65,y+85+rows.index(row)*spacing)
def terminal(x,y,label,color):
    rect(x-190,y-24,190,48,'#eff4fa','#bac9d9',8)
    text(x-100,y+8,label,23,weight=700,anchor='middle')
    dot(x,y,color)

BROWN='#8d4b24'; YELLOW='#e4b300'; BLUE='#246fd5'; RED='#d52d37'; GREEN='#198c64'; BLACK='#243447'
text(55,65,'ESP32 + breadboard LED + buzzer + PIR',43,weight=700)
text(55,109,'Complete connection picture • all ESP32 pin boxes below refer to the SAME board.',25)
text(55,146,'Unplug USB before moving wires. Follow pin names and hole labels, not wire colour alone.',23,'#9a3028',700)

# LED panel. Every lead is drawn explicitly to the named hole.
rect(40,185,1000,760)
text(70,231,'1  EXTERNAL LED — controlled by D2 / GPIO 2',29,weight=700)
terminal(305,330,'ESP32  D2',BROWN)
terminal(305,410,'ESP32  GND',YELLOW)
p=breadboard(500,245,list(range(6,14)))
line([(305,330),p('A',6)],BROWN)
dot(*p('A',6),BROWN)
text(326,310,'Brown jumper',20,BROWN,700)
e6=p('E',6); e10=p('E',10)
line([e6,e10],'#7b858d',5)
rect(e6[0]-15,390,30,80,'#e4c391','#8f6a34',5)
for yy,c in [(407,'#ba423d'),(420,'#ba423d'),(433,'#774222'),(455,'#b6983d')]:
    parts.append(f'<rect x="{e6[0]-15}" y="{yy}" width="30" height="7" fill="{c}"/>')
text(876,411,'330 Ω',20,weight=700)
dot(*e6,'#7b858d'); dot(*e10,'#7b858d')
# A real LED body with two leads bent to different rows.
line([(425,618),(425,530),p('A',10)],RED,5)
line([(455,618),(455,680),p('A',13)],BLACK,5)
parts.append('<path d="M420 608 V580 Q420 555 440 555 Q460 555 460 580 V608 Z" fill="#eb3e46" stroke="#9c1c28" stroke-width="3"/>')
rect(416,606,48,12,'#d52d37','#9c1c28',3)
text(384,570,'+',27,RED,700)
text(467,643,'−',27,BLACK,700)
text(76,567,'LED + / long leg',22,RED,700)
text(76,600,'→ A10',24,RED,700)
text(76,661,'LED − / short leg',22,BLACK,700)
text(76,694,'→ A13',24,BLACK,700)
dot(*p('A',10),RED); dot(*p('A',13),BLACK)
line([(305,410),(355,410),(355,760),(655,760),p('B',13)],YELLOW)
dot(*p('B',13),YELLOW)
text(377,790,'Yellow GND jumper → B13',22,'#8c6800',700)
text(70,842,'Exact holes: D2 → A6 • resistor E6–E10 • LED + A10 / − A13 • GND → B13',21,weight=700)
text(70,880,'A–E holes in the SAME numbered row connect internally. Different rows are separate.',21)
text(70,915,'The LED legs must be in different rows. The resistor can face either way.',21)

# Buzzer panel; separately positioned legs, no reliance on split power rails.
rect(40,975,1000,460)
text(70,1020,'2  BUZZER — two separate breadboard rows',29,weight=700)
terminal(305,1120,'ESP32  D4',BLUE)
terminal(305,1200,'ESP32  GND',YELLOW)
q=breadboard(500,1060,list(range(19,23)),50)
line([(305,1120),(365,1120),(365,1095),(480,1095),(480,1145),q('B',19)],BLUE)
dot(*q('B',19),BLUE)
line([(305,1200),(355,1200),(355,1340),(655,1340),q('B',22)],YELLOW)
dot(*q('B',22),YELLOW)
circle(445,1170,42,'#29343e','#111a24',3)
circle(445,1170,6,'#e1c995')
text(419,1166,'+',23,'#ffffff',700)
text(463,1191,'−',23,'#ffffff',700)
line([(425,1206),(425,1145),q('A',19)],BLUE,5)
line([(465,1206),(465,1295),q('A',22)],BLACK,5)
dot(*q('A',19),BLUE); dot(*q('A',22),BLACK)
text(70,1280,'Buzzer + → A19',22,BLUE,700)
text(70,1314,'Buzzer − → A22',22,BLACK,700)
text(70,1382,'D4 → B19 • GND → B22. Keep the buzzer legs in DIFFERENT rows.',22,weight=700)
text(70,1413,'Use the + mark on the buzzer to identify its positive leg.',21)

# PIR panel — abstract terminals deliberately do not claim a physical pin order.
rect(1070,185,490,1250)
text(1100,232,'3  PIR MOTION SENSOR',28,weight=700)
text(1100,278,'HC-SR501: place beside the board.',22)
text(1100,310,'Wire its three labelled pins directly.',22)
rect(1145,385,340,365,'#236b53','#164b3a',14)
circle(1315,505,98,'#f0f2f0','#c9d0cc',3)
for xx,yy in [(1270,474),(1330,461),(1260,530),(1330,531),(1310,496)]:
    circle(xx,yy,22,'#e5eae6','#d0d8d2')
rect(1180,641,55,35,'#dcb649','#998328',4)
rect(1420,641,40,35,'#dcb649','#998328',4)
text(1315,718,'PIR SENSOR',25,'#ffffff',700,anchor='middle')
for x,label,c,end_y in [(1190,'VCC',RED,1040),(1315,'OUT',GREEN,1150),(1440,'GND',BLACK,1040)]:
    text(x,792,label,24,c,700,anchor='middle')
    dot(x,815,c)
    line([(x,815),(x,end_y)],c)
    dot(x,end_y,c)
rect(1130,1040,370,220,'#eff4fa','#bac9d9',12)
line([(1315,815),(1315,1150)],GREEN)
# Redraw the endpoints on the named ESP32 terminals over the block.
dot(1190,1040,RED); dot(1315,1150,GREEN); dot(1440,1040,BLACK)
text(1190,1080,'VIN',24,RED,700,anchor='middle')
text(1190,1111,'5V via USB',17,RED,anchor='middle')
text(1440,1080,'GND',24,BLACK,700,anchor='middle')
text(1315,1190,'D5 / GPIO 5',24,GREEN,700,anchor='middle')
text(1315,1232,'ESP32 pins',22,weight=700,anchor='middle')
text(1100,1310,'Match the labels on YOUR PIR.',22,weight=700)
text(1100,1345,'Pin order here is schematic;',22)
text(1100,1376,'check its printed labels before wiring.',21)
text(1100,1410,'Do not connect PIR VCC to D5.',21,'#9a3028',700)

# Exact physical header locator for the photographed 30-pin ESP32.
rect(40,1465,490,535)
text(70,1508,'FIND THE PINS ON YOUR ESP32',24,weight=700)
text(70,1540,'Front / component side • USB at the TOP',20)
rect(190,1580,190,375,'#263142','#111b29',12)
rect(253,1555,64,51,'#cbd0d3','#9ca6af',4)
rect(226,1768,120,116,'#aeb9ba','#829393',4)
text(286,1825,'ESP32',22,'#263142',700,anchor='middle')
left=['3V3','GND','D15','D2','D4','RX2','TX2','D5','D18','D19','D21','RX0','TX0','D22','D23']
right=['VIN','GND','D13','D12','D14','D27','D26','D25','D33','D32','D35','D34','VN','VP','EN']
for i,(l,r) in enumerate(zip(left,right)):
    yy=1608+i*22
    lc={'D2':BROWN,'D4':BLUE,'D5':GREEN,'GND':'#a87d00'}.get(l,'#617187')
    rc={'VIN':RED,'GND':'#a87d00'}.get(r,'#617187')
    circle(200,yy,5,lc); circle(370,yy,5,rc)
    text(181,yy+6,l,18,lc,700 if l in ['D2','D4','D5','GND'] else 400,anchor='end')
    text(389,yy+6,r,18,rc,700 if r in ['VIN','GND'] else 400)
text(70,1978,'Use printed labels, not counted pin positions.',20,weight=700)

rect(560,1465,1000,535)
text(592,1515,'BEFORE YOU TEST',30,weight=700)
for i,s in enumerate([
    '1. Unplug USB and rebuild ONE external LED circuit first.',
    '2. Add the buzzer in rows 19 and 22, then wire the PIR.',
    '3. Female jumper end → ESP32 pin. Male end → breadboard hole.',
    '4. Plug USB in; close Arduino Serial Monitor; connect the app.',
    '5. In Sensors & lights, press Full brightness to check the LED.',
    '6. Switch Buzzer on and press Run test to check both.'
]): text(592,1564+i*42,s,23)
rect(590,1820,940,115,'#fff2d9','#e6c787',12)
text(612,1855,'WHY THE ESP32 LIGHTS UP BUT THE EXTERNAL LED DOES NOT',22,'#704919',700)
text(612,1890,'Your sketch drives D2. Onboard light activity does not verify the external circuit.',21)
text(612,1921,'Check LED polarity, the series resistor, hole numbers, and the GND connection.',21)
text(592,1970,'Do not connect a bare LED directly to D2 or 3V3. Keep the series resistor.',21,'#9a3028',700)

parts.append('</svg>')
(out/'esp32-complete-connections.svg').write_text('\n'.join(parts))
print(out/'esp32-complete-connections.svg')
