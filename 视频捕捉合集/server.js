/* ================================================================
 * 备用本地服务器(零依赖版)
 * ----------------------------------------------------------------
 * 这个文件是「一键启动.cmd」的后备方案:
 *   - 电脑装了 Python  → 优先用 Python 自带的 http.server,本文件用不上
 *   - 只有 Node.js     → 才会用这个文件启动
 *
 * 它不依赖任何第三方库,只用 Node.js 内置的 http / fs / path 模块,
 * 作用和 Python 的 http.server 一样:把当前文件夹变成一个小网站,
 * 让浏览器能通过 http://localhost:8000/ 访问页面并使用摄像头。
 *
 * 启动方式:node server.js [端口号],默认端口 8000
 * ================================================================ */

const http = require('http');
const fs = require('fs');
const path = require('path');

// 端口号:优先用命令行传入的(比如 node server.js 9000),否则用 8000
const PORT = Number(process.argv[2]) || 8000;

// 不同文件扩展名对应的 Content-Type(告诉浏览器这是什么类型的文件)
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif':  'image/gif',
  '.webp': 'image/webp',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
  '.wasm': 'application/wasm',      // MediaPipe 的 WASM 运行时
  '.tflite': 'application/octet-stream', // AI 模型文件
  '.data': 'application/octet-stream',
  '.bin':  'application/octet-stream',
  '.binarypb': 'application/octet-stream'
};

const server = http.createServer((req, res) => {
  // 去掉网址里的查询参数(?xxx=yyy),并把 URL 解码成正常中文路径
  let urlPath = decodeURIComponent(req.url.split('?')[0]);

  // 访问根目录时,默认返回 index.html(菜单页)
  if (urlPath === '/') urlPath = '/index.html';

  // 拼出文件在硬盘上的真实路径
  const filePath = path.join(__dirname, urlPath);

  // 安全检查:防止通过 ../ 访问项目文件夹之外的文件
  if (!filePath.startsWith(__dirname)) {
    res.writeHead(403);
    return res.end('403 Forbidden');
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('404 Not Found: ' + urlPath);
    }
    // 根据扩展名告诉浏览器文件类型;模型文件不缓存,方便调试
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': 'no-cache'
    });
    res.end(data);
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('============================================================');
  console.log('  摄像头互动小课堂 服务器已启动');
  console.log('  请用浏览器打开: http://localhost:' + PORT + '/index.html');
  console.log('  上课期间请保持本窗口开启,按 Ctrl+C 或关窗即停止');
  console.log('============================================================');
});
