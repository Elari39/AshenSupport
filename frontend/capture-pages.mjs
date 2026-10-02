import { chromium } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir,writeFile } from 'node:fs/promises'
import path from 'node:path'
const root=path.resolve('..'),folder=path.join(root,'output/screenshots')
await mkdir(folder,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH})
const context=await browser.newContext({viewport:{width:1440,height:1000}})
const page=await context.newPage()
const errors=[]
page.on('pageerror',e=>errors.push(e.message))
let audit=null
try{
  for(const route of ['support','tasks','tickets','login']){
    await page.goto(`http://localhost:8180/${route}`)
    await page.locator('h1').waitFor()
    await page.screenshot({path:path.join(folder,`${route}-desktop.png`),fullPage:true})
  }
  // Ephemeral local admin session for visual QA. Token never leaves this process or appears in logs.
  const setup="import json,secrets; from datetime import timedelta; from app.db import SessionLocal,User,Session,now; from app.security import digest; from argon2 import PasswordHasher; db=SessionLocal(); u=User(username='visual-'+secrets.token_hex(6),password_hash=PasswordHasher().hash(secrets.token_urlsafe(32))); db.add(u); db.flush(); token=secrets.token_urlsafe(32); s=Session(token_hash=digest(token),csrf=secrets.token_urlsafe(32),user_id=u.id,expires_at=now()+timedelta(hours=1)); db.add(s); db.commit(); print(json.dumps({'user':u.id,'session':s.id,'token':token})); db.close()"
  audit=JSON.parse(execFileSync('docker',['compose','exec','-T','api','python','-c',setup],{cwd:root,encoding:'utf8',windowsHide:true}))
  await context.addCookies([{name:'ashen_session',value:audit.token,domain:'localhost',path:'/',httpOnly:true,sameSite:'Lax'}])
  for(const route of ['admin/knowledge','admin/usage']){
    await page.goto(`http://localhost:8180/${route}`)
    await page.locator('h1').waitFor()
    await page.waitForTimeout(400)
    await page.screenshot({path:path.join(folder,`${route.replace('/','-')}-desktop.png`),fullPage:true})
  }
  const measurements=[]
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000})
    for(const route of ['support','tasks','tickets','login','admin/knowledge','admin/usage']){
      await page.goto(`http://localhost:8180/${route}`)
      await page.locator('h1').waitFor()
      const measure=await page.evaluate(()=>{const panel=document.querySelector('.panel');const style=panel?getComputedStyle(panel):null;return{width:innerWidth,scrollWidth:document.documentElement.scrollWidth,border:style?.borderTopWidth,radius:style?.borderRadius,shadow:style?.boxShadow}})
      measurements.push({route,...measure})
      if(measure.scrollWidth>width)throw new Error(`Overflow on ${route} at ${width}`)
      if(width===390)await page.screenshot({path:path.join(folder,`${route.replace('/','-')}-mobile.png`),fullPage:true})
    }
  }
  if(errors.length)throw new Error(errors.join('\n'))
  await writeFile(path.join(folder,'measurements.json'),JSON.stringify(measurements,null,2))
  console.log(`Captured six pages; no overflow at 390/768/1440; ${errors.length} page errors.`)
}finally{
  if(audit){const cleanup=`from app.db import SessionLocal,User,Session; db=SessionLocal(); db.delete(db.get(Session,'${audit.session}')); db.flush(); db.delete(db.get(User,'${audit.user}')); db.commit(); db.close()`;execFileSync('docker',['compose','exec','-T','api','python','-c',cleanup],{cwd:root,windowsHide:true})}
  await browser.close()
}
