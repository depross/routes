import re, sys, cairosvg
page=open(sys.argv[1]).read()
svg=re.search(r'<svg class="map has-streets".*?</svg>', page, re.S).group(0)
css=re.search(r'<style>\s*/\* One narrow.*?</style>', page, re.S).group(0)
rules="\n".join(l for l in css.splitlines() if l.strip().startswith('.map .') or l.strip().startswith('.map.has'))
vars_={'--bg':'#000000','--fg':'#EDE8E1','--muted':'#A8A197','--dim':'#7C756D','--line':'#2A2724','--orange':'#E85D1F','--now':'#4A8CFF','--font-body':'sans-serif','--font-accent':'serif'}
for k,v in vars_.items(): rules=rules.replace('var(%s)'%k, v)
rules=rules.replace('.map .','svg .').replace('.map.has-streets','svg').replace('filter: drop-shadow(0 0 6px rgba(232,93,31,.7));','')
out=svg.replace('<defs>','<style>%s</style><defs>'%rules,1)
out=out.replace('<rect width="600" height="600" fill="url(#dots)"/>','<rect width="600" height="600" fill="#060505"/><rect width="600" height="600" fill="url(#dots)"/>',1)
out=out.replace(' hidden>',' display="none">').replace('&','&amp;')
cairosvg.svg2png(bytestring=out.encode(), write_to=sys.argv[2], output_width=1200, output_height=1200)
print('rendered', sys.argv[2])
