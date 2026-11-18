from pathlib import Path
file=Path('deploy/web/collector.html');text=file.read_text(encoding='utf-8')
text=text.replace("['enddate','结束日期参数'],['captcha'","['enddate','结束日期参数'],['username','账号（运行时注入）'],['password','密码（运行时注入）'],['captcha'")
text=text.replace('const bindings={},defaults={},captcha_paths=[];','const bindings={},secret_bindings={},defaults={},captcha_paths=[];')
text=text.replace("if(key==='captcha'){captcha_paths.push(item.input.path)}else if(key)","if(key==='captcha'){captcha_paths.push(item.input.path)}else if(['username','password'].includes(key)){(secret_bindings[key]??=[]).push(item.input.path)}else if(key)")
text=text.replace('bindings,defaults,captcha_paths,checks:','bindings,secret_bindings,defaults,captcha_paths,checks:')
if 'id="maxun-login-step"' not in text:
    extra='''<details class="callout"><summary>登录验证码重试与原始文件下载</summary><p class="help">步骤选自当前真实录制；图片和提示选择器请从兼容视图或实际网页核对。</p><label>登录提交步骤<select id="maxun-login-step"><option value="">不配置登录重试</option></select></label><label>验证码图片选择器<input id="maxun-captcha-image" placeholder="从真实页面复制"></label><label>登录成功页面<select id="maxun-login-success"><option value="">请选择实际录制到的页面</option></select></label><label>登录错误提示选择器<input id="maxun-login-error" placeholder="从真实页面核对"></label><label>文件下载步骤（可多选）<select id="maxun-download-steps" multiple></select></label><label>日期校验列（逗号分隔）<input id="maxun-date-columns" placeholder="例如：时间"></label></details>'''
    text=text.replace('<div id="maxun-inputs"></div>','<div id="maxun-inputs"></div>'+extra)
    callback="""$('maxun-robot').addEventListener('change',()=>{const robot=maxunRobots.find(r=>r.id===$('maxun-robot').value);for(const id of ['maxun-login-step','maxun-login-success','maxun-download-steps'])$(id).replaceChildren();const option=element('option','不配置登录重试',$('maxun-login-step'));option.value='';for(const click of robot?.clicks||[]){for(const id of ['maxun-login-step','maxun-download-steps']){const o=element('option',click.path+' · '+click.selector,$(id));o.value=click.path}}for(const url of robot?.urls||[]){const o=element('option',url,$('maxun-login-success'));o.value=url}});
"""
    text=text.replace("$('publish-maxun').onclick=",callback+"$('publish-maxun').onclick=")
    before="const result=await api('maxun/publish',"
    after="""const robot=maxunRobots.find(r=>r.id===$('maxun-robot').value),submit_path=$('maxun-login-step').value;let login;if(submit_path){const captcha=robot.inputs.find(input=>captcha_paths.includes(input.path));if(!captcha||!$('maxun-captcha-image').value.trim()||!$('maxun-login-success').value||!$('maxun-login-error').value.trim())throw Error('请完整配置验证码输入、图片、成功页面和错误提示');login={submit_path,captchaSelector:captcha.selector,imageSelector:$('maxun-captcha-image').value.trim(),successUrl:$('maxun-login-success').value,errorSelector:$('maxun-login-error').value.trim()}}const download_paths=[...$('maxun-download-steps').selectedOptions].map(option=>option.value);const result=await api('maxun/publish',"""
    text=text.replace(before,after)
    text=text.replace('bindings,secret_bindings,defaults,captcha_paths,checks:','bindings,secret_bindings,defaults,captcha_paths,login,download_paths,checks:')
    text=text.replace("required_columns:$('maxun-columns').value.split(',').map(s=>s.trim()).filter(Boolean)","required_columns:$('maxun-columns').value.split(',').map(s=>s.trim()).filter(Boolean),date_columns:$('maxun-date-columns').value.split(',').map(s=>s.trim()).filter(Boolean)")
file.write_text(text,encoding='utf-8')
