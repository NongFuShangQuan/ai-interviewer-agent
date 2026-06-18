(function(){
const c=document.getElementById('particles');
if(!c)return;
const ctx=c.getContext('2d');
let w,h,particles=[];
function resize(){w=c.width=window.innerWidth;h=c.height=window.innerHeight}
window.addEventListener('resize',resize);
resize();
for(let i=0;i<60;i++){
    particles.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-0.5)*0.5,vy:(Math.random()-0.5)*0.5,r:Math.random()*2+1,a:Math.random()*0.3+0.1});
}
function draw(){
    ctx.clearRect(0,0,w,h);
    particles.forEach(p=>{
        p.x+=p.vx;p.y+=p.vy;
        if(p.x<0)p.x=w;if(p.x>w)p.x=0;if(p.y<0)p.y=h;if(p.y>h)p.y=0;
        ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
        ctx.fillStyle=`rgba(102,126,234,${p.a})`;ctx.fill();
    });
    for(let i=0;i<particles.length;i++){
        for(let j=i+1;j<particles.length;j++){
            const dx=particles[i].x-particles[j].x,dy=particles[i].y-particles[j].y;
            const d=Math.sqrt(dx*dx+dy*dy);
            if(d<150){
                ctx.beginPath();ctx.moveTo(particles[i].x,particles[i].y);ctx.lineTo(particles[j].x,particles[j].y);
                ctx.strokeStyle=`rgba(102,126,234,${0.08*(1-d/150)})`;ctx.stroke();
            }
        }
    }
    requestAnimationFrame(draw);
}
draw();
})();