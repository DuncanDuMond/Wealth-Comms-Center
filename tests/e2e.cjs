const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const baseURL = process.env.WEALTH_TEST_URL || 'http://127.0.0.1:8765';
  const browser = await chromium.launch({headless:true, ...(process.env.PW_CHANNEL ? {channel:process.env.PW_CHANNEL} : {})});
  const context = await browser.newContext({viewport:{width:1440,height:1000}, locale:'en-US'});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const email = `browser-${Date.now()}@example.test`;
  const password = 'Synthetic-test-password-2026!';
  let registered = false;
  fs.mkdirSync('test-results', {recursive:true});
  try {
    await page.goto(baseURL);
    await page.locator('[data-action="auth-register"]').click();
    await page.locator('#auth-form [name="email"]').fill(email);
    await page.locator('#auth-form [name="password"]').fill(password);
    await page.locator('#auth-form button[type="submit"]').click();
    await page.locator('#profile-form').waitFor();
    registered = true;
    await page.locator('#profile-form [name="name"]').fill('Example · 東京');
    await page.locator('#place-query-profile').fill('東京');
    await page.locator('[data-search-place="profile"]').click();
    await page.locator('.place-result').first().click();
    await page.locator('#profile-form [name="birth_date"]').fill('1990-06-15');
    await page.locator('#profile-form [name="birth_time"]').fill('10:30:00');
    assert.equal(await page.locator('#profile-form [name="timezone"]').inputValue(),'Asia/Tokyo');
    assert(Number(await page.locator('#profile-form [name="latitude"]').inputValue())>35);
    await page.locator('#profile-form button[type="submit"]').click();
    await page.locator('.score-value').waitFor({timeout:30000});
    await page.screenshot({path:'test-results/overview-desktop.png',fullPage:true});
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    const profiles = await (await context.request.get(`${baseURL}/api/profiles`)).json();
    assert.equal(profiles.length,1);
    const profile = profiles[0];
    const report = await (await context.request.get(`${baseURL}/api/profiles/${profile.id}/report`)).json();
    assert(report.chart.bodies.some(body => body.name === 'Sun'));
    const svg = await context.request.get(`${baseURL}/api/profiles/${profile.id}/cards/sun?format=svg&locale=ja`);
    assert.equal(svg.status(),200);
    assert((await svg.text()).includes('<svg'));
    for (const locale of ['ja','zh-CN','th','ko','vi','en']) {
      await page.locator('#language').selectOption(locale);
      assert.equal(await page.locator('html').getAttribute('lang'),locale);
      assert.equal(await page.locator('body').innerText().then(t=>t.includes('undefined')),false);
    }
    await page.locator('[data-view="map"]').first().click();
    await page.locator('.leaflet-container').waitFor();
    await page.locator('.leaflet-overlay-pane canvas').waitFor();
    const geography = await (await context.request.get(`${baseURL}/api/profiles/${profile.id}/map`)).json();
    assert.equal(geography.features.length,40);
    await page.locator('.leaflet-container').click({position:{x:240,y:200}});
    await page.locator('#save-location [name="title"]').fill('Example saved place');
    await page.locator('#save-location button[type="submit"]').click();
    await page.getByText('Example saved place',{exact:true}).first().waitFor();
    await page.screenshot({path:'test-results/map-desktop.png',fullPage:true});
    await page.locator('[data-view="journal"]').first().click();
    await page.locator('[data-action="new-entry"]').click();
    await page.locator('#journal-form [name="title"]').fill('Test a practical assumption');
    await page.locator('#journal-form [name="body"]').fill('Take one small action and record the result.');
    await page.locator('#journal-form [name="outcome"]').fill('Observed result, not a prediction.');
    await page.locator('#journal-form button[type="submit"]').click();
    await page.getByText('Test a practical assumption',{exact:true}).waitFor();
    await page.locator('.equation-panel > summary').click();
    await page.locator('#equation-form [name="capital"]').fill('50');
    await page.locator('#equation-form [name="human"]').fill('60');
    await page.locator('#equation-form button[value="calculate"]').click();
    await page.locator('.equation-result').waitFor();
    await page.locator('#equation-form button[value="save"]').click();
    await page.getByText('Personal equation experiment',{exact:true}).waitFor();
    await page.locator('[data-view="agent"]').first().click();
    await page.locator('#agent-question').fill('What is one practical goal to work on today?');
    await page.locator('#agent-form button[type="submit"]').click();
    await page.waitForFunction(()=>document.body.innerText.includes('Local guide:'));
    assert((await page.locator('body').innerText()).includes('[score.symbolic]'));
    const mobile = await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,locale:'ja-JP',storageState:await context.storageState()});
    const phone = await mobile.newPage();
    phone.on('pageerror',error=>errors.push(error.message));
    await phone.goto(baseURL);
    await phone.locator('.score-value').waitFor({timeout:30000});
    for(const locale of ['ja','zh-CN','th','ko','vi']) {
      await phone.locator('#language').selectOption(locale);
      assert(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1), `Horizontal overflow in ${locale}`);
    }
    await phone.locator('#language').selectOption('ja');
    await phone.screenshot({path:'test-results/overview-mobile-ja.png',fullPage:false});
    await phone.locator('#cosmic-preview').scrollIntoViewIfNeeded();
    await phone.waitForFunction(()=>document.querySelector('#cosmic-preview')?.naturalWidth>0);
    await phone.screenshot({path:'test-results/cosmic-card-mobile-ja.png',fullPage:false});
    await mobile.close();
    const exported = await (await context.request.get(`${baseURL}/api/export`)).json();
    assert.equal(exported.profiles.length,1);
    assert(exported.journal.length>=2);
    assert.deepEqual(errors,[]);
    console.log('PASS: signup, city search, profile, real report, six languages, map, saved location, journal, equation, guide, SVG preview/export, account export, mobile overflow, no JavaScript errors.');
  } catch(error) {
    await page.screenshot({path:'test-results/failure.png',fullPage:true}).catch(()=>{});
    console.error(error);
    process.exitCode=1;
  } finally {
    if(registered) {
      const removed=await context.request.delete(`${baseURL}/api/account`,{data:{email,password},headers:{'X-Wealth-Request':'1'}});
      assert.equal(removed.status(),200,'Synthetic test account cleanup failed');
    }
    await browser.close();
  }
})();
