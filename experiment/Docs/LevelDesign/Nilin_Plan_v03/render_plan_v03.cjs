const sharp=require("C:\\Users\\21475\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\sharp");
sharp("D:\\game design\\experiment\\Docs\\LevelDesign\\Nilin_Plan_v03\\逆鳞_登山关卡平面图_v03.svg").png().toFile("D:\\game design\\experiment\\Docs\\LevelDesign\\Nilin_Plan_v03\\逆鳞_登山关卡平面图_v03.png").then(()=>console.log('rendered'));
