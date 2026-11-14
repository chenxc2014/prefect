// 在线设计器的通用日期输入与图片验证码动作，秘密值不写入日志。
const crypto = require('crypto');
const decrypt = value => {
  const [iv, body] = value.split(':');
  const cipher = crypto.createDecipheriv('aes-256-cbc', Buffer.from(process.env.ENCRYPTION_KEY, 'hex'), Buffer.from(iv, 'hex'));
  return Buffer.concat([cipher.update(Buffer.from(body, 'hex')), cipher.final()]).toString();
};
function locate(page, selector) {
  // 选择器来自真实网页的录制记录；跨框架优先由录制器保存的路径解析。
  const parts = selector.split(/\s*>>\s*/);
  let context = page;
  while (parts.length > 1) context = context.frameLocator(parts.shift());
  return context.locator(parts[0]).first();
}
exports.install = page => {
  page.platformInputDate = async (selector, encrypted) => {
    const target = locate(page, selector);
    await target.evaluate((element, value) => {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      descriptor.set.call(element, value);
      for (const name of ['input', 'change', 'blur']) element.dispatchEvent(new Event(name, {bubbles: true}));
      element.blur();
    }, decrypt(encrypted));
  };
  page.platformCaptcha = async selector => {
    const input = locate(page, selector);
    const imagePath = await input.evaluate(element => {
      const box = element.getBoundingClientRect();
      let root = element.closest('form') || element.parentElement;
      let candidates = [];
      for (let depth = 0; root && depth < 6; depth++, root = root.parentElement) {
        candidates = [...root.querySelectorAll('canvas,img')].filter(node => {
          const rect = node.getBoundingClientRect();
          return rect.width >= 30 && rect.height >= 15 && rect.width <= 500 && rect.height <= 200 && getComputedStyle(node).visibility !== 'hidden';
        });
        if (candidates.length) break;
      }
      if (!candidates.length) throw new Error('未在验证码输入框附近找到图片，请重新录制或补充配置');
      const distance = node => {const r=node.getBoundingClientRect();return Math.abs(r.y-box.y)*2+Math.abs(r.x-box.x)};
      const node = candidates.sort((a,b) => distance(a)-distance(b))[0];
      const parts=[];
      for (let current=node; current && current.nodeType===1; current=current.parentElement) {
        if (current.id) {parts.unshift('#'+CSS.escape(current.id));break}
        const siblings=current.parentElement ? [...current.parentElement.children].filter(x=>x.tagName===current.tagName) : [current];
        parts.unshift(current.tagName.toLowerCase()+':nth-of-type('+(siblings.indexOf(current)+1)+')');
      }
      return parts.join(' > ');
    });
    const frame = await (await input.elementHandle()).ownerFrame();
    const image = frame.locator(imagePath);
    const content = await image.screenshot();
    const response = await fetch('http://host.docker.internal:18767/recognize', {
      method:'POST',headers:{'Content-Type':'image/png','x-api-key':process.env.CRAWLER_OCR_KEY},body:content
    });
    if (!response.ok) throw new Error('图片验证码识别服务未成功返回');
    const result = await response.json();
    await input.fill(result.text);
  };
};
