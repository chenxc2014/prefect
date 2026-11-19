// 使用真实界面验证维护入口，删除请求仅在测试浏览器内拦截。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';

const require = createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium, expect} = require('@playwright/test');
const config = JSON.parse(fs.readFileSync('.local/client.json', 'utf8'));
const auth = config.env.PREFECT_API_AUTH_STRING;
const split = auth.indexOf(':');
const base = 'http://127.0.0.1:18843';
const maxun = 'http://127.0.0.1:19943';
const preview = process.argv.includes('--preview');
const liveRecording = process.argv.includes('--live-recording');
const browser = await chromium.launch({channel:'chrome', headless:true});

try {
  const context = await browser.newContext({locale:'zh-CN', viewport:{width:1440,height:950}});
  const errors = [];
  context.on('page', target => target.on('pageerror', error => errors.push(error.message)));
  if (preview) {
    await context.route(maxun + '/_platform/theme.js', async route => {
      const response = await route.fetch();
      const source = await response.text();
      const marker = '// 由采集平台提供明确关联';
      const offset = source.indexOf(marker);
      if (offset < 0) throw Error('找不到原有业务关联脚本');
      await route.fulfill({response, body:source.slice(0,offset) + fs.readFileSync('deploy/web/maxun-task-links.js','utf8')});
    });
    await context.route(maxun + '/_platform/theme.css', route => route.fulfill({
      contentType:'text/css; charset=utf-8', body:fs.readFileSync('deploy/web/suite-theme.css','utf8'),
    }));
  }
  const page = await context.newPage();
  await page.goto(base + '/collector/');
  await page.locator('[name="username"]').fill(auth.slice(0,split));
  await page.locator('[name="password"]').fill(auth.slice(split+1));
  await page.getByRole('button',{name:'登录统一工作台',exact:true}).click();
  await page.waitForURL(base + '/collector/');
  const snapshot = await (await context.request.get(base + '/collector/api/maxun/relations')).json();
  const group = snapshot.groups.find(item => item.task_name === '老百姓 · 配送数据');
  const draft = group?.drafts.find(item => !item.missing);
  if (!draft) throw Error('没有找到现有老百姓配送设计稿');

  await page.goto(base + '/collector/open/maxun');
  await page.waitForURL(maxun + '/robots');
  const card = page.locator('.mx-rel-group').filter({has:page.getByRole('heading',{name:group.task_name,exact:true})});
  const editing = context.waitForEvent('page');
  await card.getByRole('link',{name:'编辑设计稿 ↗',exact:true}).click();
  const editor = await editing;
  await editor.waitForURL(maxun + '/robots/' + draft.id + '/edit');
  const panel = editor.locator('.mx-draft-maintenance');
  const basic = panel.getByRole('button',{name:'基本设置',exact:true});
  const retrain = panel.getByRole('button',{name:'重新录制',exact:true});
  const save = editor.getByRole('button',{name:'保存更改',exact:true});
  await expect(basic).toHaveAttribute('aria-pressed','true');
  await expect(save).toBeVisible();
  const nameInput = editor.getByLabel('更改机器人名称',{exact:true});
  await expect(nameInput).toHaveValue(draft.name);
  await nameInput.fill('浏览器临时验证');
  await retrain.click();
  await expect(save).toBeHidden();
  await expect(panel.getByText(/包含平台适配|含平台适配/)).toBeVisible();
  await basic.click();
  await expect(nameInput).toHaveValue('浏览器临时验证');
  await expect(save).toBeVisible();
  await nameInput.fill(draft.name);
  console.log('基本设置和重新录制可切换，原有表单和未保存输入均保留');

  const duplicate = context.waitForEvent('page');
  await panel.getByRole('link',{name:'复制机器人',exact:true}).click();
  const copy = await duplicate;
  await copy.waitForURL(maxun + '/robots/' + draft.id + '/duplicate');
  await expect(copy.getByText('复制机器人',{exact:true}).first()).toBeVisible();
  await copy.close();
  console.log('复制入口打开当前设计稿的 Maxun 原生复制页');

  let deleteChecks = 0, deletes = 0;
  await editor.route(maxun + '/storage/recordings/' + draft.id, route => {
    if (route.request().method() === 'DELETE') {deletes++; return route.fulfill({json:true});}
    return route.fallback();
  });
  let runCount = 1;
  await editor.route(maxun + '/storage/recordings/' + draft.id + '/runs', route => {
    deleteChecks++;
    return route.fulfill({json:{runs:{totalCount:runCount}}});
  });
  const deleteButton = panel.getByRole('button',{name:'删除机器人',exact:true});
  const dialog = editor.getByRole('dialog',{name:'删除机器人'});
  await deleteButton.click();
  await expect(dialog).toContainText(draft.name);
  await dialog.getByRole('button',{name:'取消',exact:true}).click();
  await expect(dialog).toBeHidden();
  if (deleteChecks || deletes) throw Error('取消删除触发了请求');
  await deleteButton.click();
  await dialog.getByRole('button',{name:'确认删除',exact:true}).click();
  await expect(dialog.getByRole('status')).toContainText('有关联的运行记录，无法删除');
  if (deleteChecks !== 1 || deletes) throw Error('运行记录阻止删除的规则失效');
  await dialog.getByRole('button',{name:'取消',exact:true}).click();
  console.log('取消删除没有发起请求，有运行记录时阻止删除');

  await retrain.click();
  const availability = maxun + '/record/can-create/recording';
  await editor.route(availability, route => route.fulfill({json:{canCreate:false}}));
  await panel.getByRole('button',{name:'开始重新录制',exact:true}).click();
  await expect(panel.locator('.mx-draft-status')).toContainText('已有录制会话');
  await editor.unroute(availability);
  await editor.route(availability, route => route.fulfill({json:{canCreate:true}}));
  // 保留真实的弹窗导航和会话参数，在启动后台录制之前停止。
  await context.route(maxun + '/recording-setup?session=*', route => route.fulfill({
    contentType:'text/html; charset=utf-8', body:'<title>录制入口验收</title>',
  }));
  const recording = context.waitForEvent('page');
  await panel.getByRole('button',{name:'开始重新录制',exact:true}).click();
  const recordingPage = await recording;
  await recordingPage.waitForURL(url => url.pathname === '/recording-setup');
  const session = await recordingPage.evaluate(() => ({
    robot:sessionStorage.getItem('robotToRetrain'), name:sessionStorage.getItem('robotName'),
    url:sessionStorage.getItem('recordingUrl'),id:sessionStorage.getItem('recordingSessionId'),
  }));
  if(session.robot !== draft.id || session.name !== draft.name || !/^https:\/\/scep\.lbxcn\.com\//.test(session.url)
    || new URL(recordingPage.url()).searchParams.get('session') !== session.id) throw Error('重新录制未传递正确的原始机器人');
  await recordingPage.close();
  console.log('存在录制时给出提示，空闲时将正确设计稿交给 Maxun 录制入口');

  if (liveRecording) {
    await editor.unroute(availability);
    await context.unroute(maxun + '/recording-setup?session=*');
    const active = async () => {
      const response = await context.request.get(maxun + '/record/active');
      if(!response.ok()) throw Error('真实录制状态接口返回 HTTP '+response.status());
      const body = (await response.text()).trim();
      if (body === '' || body === 'null') return '';
      if (!/^[a-f0-9-]{36}$/i.test(body)) throw Error('真实录制状态接口响应格式异常');
      return body;
    };
    const current = await active();
    if (current) {
      await panel.getByRole('button',{name:'开始重新录制',exact:true}).click();
      await expect(panel.locator('.mx-draft-status')).toContainText('已有录制会话');
      if (await active() !== current) throw Error('原有录制会话发生变化');
      console.log('真实环境已有录制，维护页保留当前会话并提示用户');
    } else {
      let owned = '';
      const created = context.waitForEvent('response',{predicate:r => r.url() === maxun + '/record/start' && r.ok(),timeout:45000});
      // 避免弹窗失败时，后台响应等待先产生未处理拒绝。
      created.catch(() => {});
      const popup = context.waitForEvent('page');
      let live;
      try {
        await panel.getByRole('button',{name:'开始重新录制',exact:true}).click();
        live = await popup;
        const response = await created;
        if (response.request().frame().page() !== live) throw Error('无法确认录制会话归属');
        owned = (await response.text()).trim();
        if (!/^[a-f0-9-]{36}$/i.test(owned)) throw Error('未取得本次录制编号');
        await live.waitForURL(maxun + '/recording');
        await expect.poll(async () => (await (await context.request.get(maxun + '/record/active/url')).text()).trim(),{
          timeout:90000, intervals:[1000,2000,3000],
        }).toMatch(/^https:\/\/scep\.lbxcn\.com\/(?:user\/login|portals\/home)/);
        console.log('旧设计稿对应的真实 Maxun 录制窗口已加载供应商页面，未保存录制');
      } finally {
        if (owned && await active() === owned) {
          const stopped = await context.request.get(maxun + '/record/stop/' + owned);
          if (!stopped.ok()) throw Error('本次验收录制会话未成功释放');
        }
        await live?.close();
      }
    }
  }

  await editor.setViewportSize({width:390,height:844});
  await expect(panel).toBeVisible();
  if (await editor.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) throw Error('小屏幕维护页横向溢出');
  runCount = 0;
  await deleteButton.click();
  await dialog.getByRole('button',{name:'确认删除',exact:true}).click();
  await editor.waitForURL(maxun + '/robots');
  if (deleteChecks !== 2 || deletes !== 1) throw Error('确认删除未对正确的机器人发起请求');
  const unchanged = await context.request.get(maxun + '/storage/recordings/' + draft.id);
  if ((await unchanged.json())?.recording_meta?.id !== draft.id) throw Error('验收改变了真实设计稿');
  console.log('确认删除只请求当前设计稿，成功时返回机器人列表，真实记录未删除');
  if (errors.length) throw Error('页面脚本异常：'+errors.join(' / '));
  console.log('桌面和手机布局通过检查，验收未保存、删除或运行任何机器人');
} finally {
  await browser.close();
}
