// Records the real local browser at one frame/second for a three-minute silent walkthrough.
// Requires Chrome (CHROME_PATH optional) and ffmpeg on PATH. Output is ignored by Git.
import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { once } from 'node:events'
import path from 'node:path'
const folder=path.resolve('../output/demo')
await mkdir(folder,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH})
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1})
const encoder=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-vcodec','mjpeg','-framerate','1','-i','pipe:0','-c:v','libx264','-preset','fast','-r','24','-pix_fmt','yuv420p',path.join(folder,'AshenSupport-walkthrough.mp4')],{windowsHide:true})
let errors=''
encoder.stderr.on('data',data=>{errors+=data.toString()})
const completion=once(encoder,'close')
let caption='AshenSupport · 技术支持工作台 | 确定性演示引擎，不代表真实 AI 效果'
async function label(){await page.evaluate(text=>{let el=document.querySelector('#demo-caption');if(!el){el=document.createElement('div');el.id='demo-caption';document.body.append(el)}el.textContent=text;Object.assign(el.style,{position:'fixed',bottom:'0',left:'0',right:'0',padding:'14px 24px',background:'#ffe14a',color:'#171717',borderTop:'3px solid #171717',fontWeight:'800',font:'14px system-ui',zIndex:'99999'})},caption)}
try{
  await page.goto(process.env.ASHEN_E2E_URL??'http://localhost:8180/support')
  await page.getByRole('button',{name:'RAG 无法回答'}).waitFor()
  await page.screenshot({path:path.join(folder,'01-workspace.png')})
  for(let frame=0;frame<180;frame++){
    const started=Date.now()
    if(frame===25){caption='01 提交具体问题：主站正常，但 RAG 无法问答。';await page.getByRole('button',{name:'RAG 无法回答'}).click();await page.getByRole('button',{name:'开始排查'}).click()}
    if(frame===45){await page.getByRole('button',{name:'生成工单草稿'}).waitFor();caption='02 查看实际检索、模拟工具结果与可定位的文档引用。';await page.locator('.citation summary').first().click();await page.screenshot({path:path.join(folder,'02-evidence.png')})}
    if(frame===70){caption='03 生成草稿，人工审核。系统不会擅自写入 GitHub 或修改服务器。';await page.getByRole('button',{name:'生成工单草稿'}).click();await page.getByRole('button',{name:'批准并创建'}).scrollIntoViewIfNeeded()}
    if(frame===95){caption='04 明确批准后，事务性创建项目内工单。重复审批不会重复创建。';await page.getByRole('button',{name:'批准并创建'}).click()}
    if(frame===110){await page.getByRole('link',{name:'工单',exact:true}).click();await page.locator('.list-row').first().click();caption='05 工单保留诊断证据、原任务与审批记录。';await page.screenshot({path:path.join(folder,'03-ticket.png')})}
    if(frame===135){await page.goto('http://localhost:8180/support');await page.getByRole('button',{name:'信息不足',exact:false}).click();await page.getByRole('button',{name:'开始排查'}).click();caption='06 信息不足就补问。补问次数有上限，未知指标不会编造。'}
    if(frame===160){await page.getByRole('link',{name:'任务记录'}).click();caption='07 任务持久化，可恢复与追踪。在线效果评估需要真实模型凭证与人工标注。'}
    await label()
    const buffer=await page.screenshot({type:'jpeg',quality:80})
    if(!encoder.stdin.write(buffer))await once(encoder.stdin,'drain')
    if(frame%30===0)process.stdout.write(`Recorded ${frame}/180 frames\n`)
    await new Promise(resolve=>setTimeout(resolve,Math.max(0,1000-(Date.now()-started))))
  }
  encoder.stdin.end()
  const [code]=await completion
  if(code!==0)throw new Error(errors)
  await writeFile(path.join(folder,'README.md'),'# Demo recording\n\nThree-minute silent recording of actual browser interactions with explanatory captions. Uses the deterministic fake provider and simulated health data; not evidence of online AI accuracy.\n')
  process.stdout.write(`Saved ${folder}\n`)
}finally{encoder.stdin.end();await browser.close()}
