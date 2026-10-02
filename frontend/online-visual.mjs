import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
let input=''
for await(const part of process.stdin) input+=part
const {token,task_id}=JSON.parse(input)
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH})
try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}})
  await context.addCookies([{name:'ashen_session',value:token,domain:'localhost',path:'/',httpOnly:true,sameSite:'Lax'}])
  const page=await context.newPage()
  const errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.goto(`http://localhost:8180/support?task=${task_id}`)
  await page.locator('.message.assistant').first().waitFor()
  if(!(await page.locator('footer').innerText()).includes('在线模型'))throw new Error('Online mode not displayed')
  const references=await page.locator('.citation').count()
  if(!references)throw new Error('No visible evidence')
  const folder=path.resolve('../output/online')
  await mkdir(folder,{recursive:true})
  await page.screenshot({path:path.join(folder,'workspace-online.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile overflow')
  await page.screenshot({path:path.join(folder,'workspace-online-mobile.png'),fullPage:true})
  if(errors.length)throw new Error('Browser runtime errors')
  await writeFile(path.join(folder,'browser.json'),JSON.stringify({online_label:true,references,mobile_overflow:false,page_errors:errors},null,2))
  console.log(JSON.stringify({browser:'passed',references}))
}finally{await browser.close()}
