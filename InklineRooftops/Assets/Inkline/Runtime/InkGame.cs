using System.Collections.Generic;
using UnityEngine;

namespace Inkline
{
    /// <summary>Original procedural rooftop prototype; no imported art or paid assets.</summary>
    public sealed class InkGame : MonoBehaviour
    {
        public static InkGame Instance { get; private set; }
        public static readonly Color Paper = new Color(0.98f, 0.94f, 0.84f);
        public static readonly Color Ink = new Color(0.12f, 0.065f, 0.22f);
        public static readonly Color Cyan = new Color(0.04f, 0.98f, 0.88f);
        public static readonly Color Pink = new Color(1f, 0.13f, 0.48f);
        public RooftopMotor Player { get; private set; }
        public readonly List<Transform> Anchors = new List<Transform>();
        public bool Won { get; private set; }
        public int Deaths { get; private set; }
        public int Checkpoint { get; private set; }
        public bool FrameBroken { get; private set; }
        public Camera MainCamera { get; private set; }
        public float RunTime { get; private set; }
        public bool TestMode;
        public int ResetCount { get; private set; }
        public readonly Vector2[] SpawnPoints = { new Vector2(-3, 1.2f), new Vector2(25, 1.95f), new Vector2(50, 2.6f) };
        public const float FinishX = 76f;

        readonly List<Material> mats = new List<Material>();
        readonly List<Pop> pops = new List<Pop>();
        readonly List<Shard> shards = new List<Shard>();
        Transform visual, head, body, armL, armR, legL, legR;
        Transform gate;
        LineRenderer rope;
        TrailRenderer trail;
        Material paperMat, inkMat, cyanMat, pinkMat;
        float notificationUntil, flashUntil, jumpVisual, frameBurstTime;
        string notification = "";
        float cameraX = -1, cameraY = 4.3f;
        float bestX = -3;
        AudioSource speaker;
        AudioClip zipSound, landSound, winSound;
        bool lastGrounded;
        GUIStyle title, small, label, huge;
        Texture2D white;
        class Pop { public Vector3 position; public string text; public Color color; public float end; }
        class Shard { public Transform t; public Vector3 velocity; public float spin, end; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void EnsureGame()
        {
            if (FindObjectOfType<InkGame>() == null) new GameObject("INKLINE — procedural game").AddComponent<InkGame>();
        }

        void Awake()
        {
            Instance = this;
            Time.timeScale = 1;
            Time.fixedDeltaTime = 1f / 60f;
            Application.targetFrameRate = 120;
            Physics2D.gravity = new Vector2(0, -9.81f);
            paperMat = Mat(Paper, 0.08f);
            inkMat = Mat(Ink, 0.0f);
            cyanMat = Mat(Cyan, 0.05f);
            pinkMat = Mat(Pink, 0.08f);
            BuildWorld();
            BuildRunner();
            BuildCamera();
            speaker = gameObject.AddComponent<AudioSource>();
            speaker.volume = 0.18f;
            zipSound = Tone(640, 0.085f, 0.6f);
            landSound = Tone(130, 0.09f, -0.55f);
            winSound = Tone(440, 0.6f, 1.2f);
            Notify("ROOFTOPS ARE YOUR RUNWAY", 3f);
        }

        Material Mat(Color c, float dots = 0.1f)
        {
            Shader shader = Shader.Find("Inkline/PaperInk") ?? Shader.Find("Unlit/Color");
            var m = new Material(shader) { color = c };
            if (m.HasProperty("_Shade")) m.SetColor("_Shade", Color.Lerp(Ink, c, 0.2f));
            if (m.HasProperty("_Dots")) m.SetFloat("_Dots", dots);
            mats.Add(m);
            return m;
        }

        GameObject Shape(string name, PrimitiveType shape, Vector3 p, Vector3 scale, Material m, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(shape);
            go.name = name;
            go.transform.SetParent(parent == null ? transform : parent, false);
            go.transform.localPosition = p;
            go.transform.localScale = scale;
            go.GetComponent<Renderer>().sharedMaterial = m;
            var c = go.GetComponent<Collider>();
            if (c) { c.enabled = false; Destroy(c); }
            return go;
        }

        void Roof(string name, float left, float right, float top, int index)
        {
            float width = right - left;
            var m = Mat(index % 2 == 0 ? new Color(0.63f,0.53f,0.68f) : new Color(0.79f,0.65f,0.71f), 0.45f);
            var go = Shape(name, PrimitiveType.Cube, new Vector3((left+right)/2, top-5, 1), new Vector3(width,10,4.2f), m);
            go.layer = 8;
            var col = go.AddComponent<BoxCollider2D>();
            col.size = Vector2.one; // Local scale supplies the world width and height.
            Shape(name+" ink roof lip", PrimitiveType.Cube, new Vector3((left+right)/2,top-0.09f,-1.18f), new Vector3(width+0.15f,0.18f,0.16f),inkMat);
            Shape(name+" paper cap", PrimitiveType.Cube, new Vector3((left+right)/2,top+0.005f,0.6f), new Vector3(width+0.12f,0.10f,4.4f),paperMat);
            for (float x = left + 1.1f; x < right - 0.4f; x += 2.15f)
                for (float y = top - 1.6f; y > top - 8; y -= 2)
                {
                    Shape("Window ink", PrimitiveType.Cube,new Vector3(x,y,-1.14f),new Vector3(0.92f,1.12f,0.06f),inkMat);
                    Shape("Window paper", PrimitiveType.Cube,new Vector3(x+0.04f,y+0.05f,-1.19f),new Vector3(0.62f,0.82f,0.03f),paperMat);
                }
        }

        void BuildWorld()
        {
            Roof("01 / Launch roof", -10, 10, 0, 0);
            Roof("02 / Relay roof", 21, 33, 0.75f, 1);
            Roof("03 / Billboard roof", 45, 56, 1.4f, 2);
            Roof("04 / Finish roof", 68, 86, 0.6f, 3);
            AddHook(new Vector2(15.5f,9.0f), "01");
            AddHook(new Vector2(38.5f,10.2f), "02");
            AddHook(new Vector2(61.5f,10.0f), "03");
            // Depth layers are visual. All gameplay colliders are on the XY plane.
            var backA = Mat(new Color(0.86f,0.78f,0.80f), 0.14f);
            var backB = Mat(new Color(0.72f,0.65f,0.78f), 0.18f);
            var random = new System.Random(20261022);
            for (int i=0;i<33;i++)
            {
                float x = -26+i*4.2f;
                float h = 3+(float)random.NextDouble()*8;
                float z = i%2==0 ? 15 : 22;
                Shape("Distant city / no collision",PrimitiveType.Cube,new Vector3(x,h/2-5,z),new Vector3(3.3f,h,2.2f),i%2==0?backA:backB);
                Shape("Antenna",PrimitiveType.Cube,new Vector3(x,h-4.3f,z),new Vector3(0.07f,1.5f,0.07f),backB);
            }
            Shape("Warm paper sky",PrimitiveType.Quad,new Vector3(35,8,30),new Vector3(250,90,1),paperMat);
            var sun = Shape("Printed sun",PrimitiveType.Sphere,new Vector3(47,14,27),new Vector3(11,11,0.3f),Mat(new Color(1,0.77f,0.53f),0.4f));
            sun.transform.rotation = Quaternion.identity;
            WorldText("INKLINE",new Vector3(-6.3f,4.8f,0),2.0f,Ink);
            WorldText("ROOFTOPS / ISSUE 01",new Vector3(-6.1f,3.3f,0),0.5f,Ink);
            WorldText("RUN  >  JUMP  >  THWIP",new Vector3(-5.9f,2.4f,0),0.30f,Ink);
            WorldText("01",new Vector3(4,1.2f,0),0.6f,Pink);
            WorldText("RELAY",new Vector3(23.2f,3.5f,0),0.7f,Ink);
            WorldText("CHECKPOINT",new Vector3(23.2f,2.6f,0),0.3f,Ink);
            WorldText("BUILD MOMENTUM",new Vector3(46,4.8f,0),0.46f,Ink);
            WorldText("FINISH",new Vector3(75,4.5f,0),1.0f,Ink);
            WorldText("END OF ISSUE",new Vector3(75,3.3f,0),0.35f,Ink);
            CheckpointFlag(25,0.75f); CheckpointFlag(50,1.4f);
            Shape("Finish beacon",PrimitiveType.Cube,new Vector3(77.5f,2.1f,0.5f),new Vector3(0.15f,3,0.15f),inkMat);
            Shape("Finish pennant",PrimitiveType.Cube,new Vector3(78.3f,3.2f,0.5f),new Vector3(1.6f,0.8f,0.12f),pinkMat);
            gate = new GameObject("Optional speed break / pass through frame").transform;
            gate.SetParent(transform);
            gate.position = new Vector3(72,2.2f,0);
            Shape("Left border",PrimitiveType.Cube,new Vector3(-1.1f,0,0),new Vector3(0.12f,3.6f,0.12f),inkMat,gate);
            Shape("Right border",PrimitiveType.Cube,new Vector3(1.1f,0,0),new Vector3(0.12f,3.6f,0.12f),inkMat,gate);
            Shape("Top border",PrimitiveType.Cube,new Vector3(0,1.8f,0),new Vector3(2.3f,0.12f,0.12f),inkMat,gate);
            WorldText("BREAK THE FRAME",new Vector3(69.3f,5.0f,0),0.32f,Pink);
        }

        void CheckpointFlag(float x,float y)
        {
            Shape("Checkpoint post",PrimitiveType.Cube,new Vector3(x,y+0.8f,0.8f),new Vector3(0.07f,1.6f,0.07f),inkMat);
            Shape("Checkpoint flag",PrimitiveType.Cube,new Vector3(x+0.45f,y+1.3f,0.8f),new Vector3(0.9f,0.5f,0.1f),cyanMat);
        }

        void AddHook(Vector2 p, string number)
        {
            var hook = Shape("Fixed hook "+number,PrimitiveType.Sphere,new Vector3(p.x,p.y,0),new Vector3(0.48f,0.48f,0.48f),cyanMat);
            Anchors.Add(hook.transform);
            var line = new GameObject("Hook ink ring").AddComponent<LineRenderer>();
            line.transform.SetParent(hook.transform,false);
            line.useWorldSpace = false;
            line.sharedMaterial = inkMat;
            line.startWidth = line.endWidth = 0.09f;
            line.positionCount = 41;
            for(int i=0;i<41;i++) { float a=i*Mathf.PI*2/40; line.SetPosition(i,new Vector3(Mathf.Cos(a)*0.8f,Mathf.Sin(a)*0.8f,-0.1f)); }
            WorldText("HOOK "+number,new Vector3(p.x-0.6f,p.y+0.85f,0),0.28f,Ink);
            Shape("Suspension cable",PrimitiveType.Cube,new Vector3(p.x,p.y+6,1),new Vector3(0.025f,12,0.025f),inkMat);
        }

        void BuildRunner()
        {
            var go = new GameObject("Original runner / XY motor");
            go.transform.SetParent(transform);
            go.transform.position = SpawnPoints[0];
            go.AddComponent<Rigidbody2D>(); go.AddComponent<CapsuleCollider2D>();
            Player = go.AddComponent<RooftopMotor>();
            visual = new GameObject("Hand built human silhouette").transform;
            visual.SetParent(go.transform,false);
            body = Shape("Jacket",PrimitiveType.Capsule,new Vector3(0,0.1f,0),new Vector3(0.48f,0.36f,0.32f),pinkMat,visual).transform;
            Shape("Chest ink",PrimitiveType.Cube,new Vector3(0,0.13f,-0.17f),new Vector3(0.20f,0.28f,0.04f),inkMat,visual);
            head = Shape("Original masked face",PrimitiveType.Sphere,new Vector3(0,0.68f,0),new Vector3(0.4f,0.43f,0.36f),inkMat,visual).transform;
            Shape("Visor / single cyan slash",PrimitiveType.Cube,new Vector3(0.08f,0.70f,-0.19f),new Vector3(0.26f,0.08f,0.045f),cyanMat,visual);
            armL = Limb("Near arm",new Vector3(-0.26f,0.15f,-0.03f),0.48f,inkMat);
            armR = Limb("Far arm",new Vector3(0.26f,0.15f,0.05f),0.48f,inkMat);
            legL = Limb("Near leg",new Vector3(-0.13f,-0.42f,-0.02f),0.60f,inkMat);
            legR = Limb("Far leg",new Vector3(0.13f,-0.42f,0.05f),0.60f,inkMat);
            rope = new GameObject("Drawn web / physics joint owns constraint").AddComponent<LineRenderer>();
            rope.transform.SetParent(transform);
            rope.sharedMaterial = cyanMat;
            rope.positionCount = 2;
            rope.startWidth = 0.045f; rope.endWidth = 0.025f;
            rope.enabled = false;
            trail = go.AddComponent<TrailRenderer>();
            trail.sharedMaterial = pinkMat;
            trail.time = 0.14f; trail.minVertexDistance = 0.15f;
            trail.startWidth = 0.38f; trail.endWidth = 0;
            trail.emitting = false;
        }

        Transform Limb(string name,Vector3 p,float length,Material m)
        { return Shape(name,PrimitiveType.Capsule,p,new Vector3(0.14f,length/2,0.15f),m,visual).transform; }

        void BuildCamera()
        {
            foreach (var old in FindObjectsOfType<Camera>()) old.enabled = false;
            var go = new GameObject("Fixed side camera / no orbit");
            go.transform.SetParent(transform);
            MainCamera = go.AddComponent<Camera>();
            MainCamera.tag = "MainCamera";
            MainCamera.orthographic = true;
            MainCamera.orthographicSize = 7.5f;
            MainCamera.clearFlags = CameraClearFlags.SolidColor;
            MainCamera.backgroundColor = Paper;
            MainCamera.nearClipPlane = 0.1f; MainCamera.farClipPlane = 100;
            go.transform.position = new Vector3(cameraX,cameraY+3,-26);
            go.transform.rotation = Quaternion.Euler(7,0,0);
            go.AddComponent<AudioListener>();
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.R)) RestartRun();
            if (Input.GetKeyDown(KeyCode.Backspace)) Respawn(false);
            if (Input.GetKeyDown(KeyCode.F2)) ScreenCapture.CaptureScreenshot(System.IO.Path.Combine(Application.persistentDataPath,"inkline-"+System.DateTime.Now.ToString("HHmmss")+".png"));
            if (!Won) RunTime += Time.deltaTime;
            bestX = Mathf.Max(bestX,Player.transform.position.x);
            if (Player.transform.position.y < -8 || Player.transform.position.x < -15) Respawn(true);
            Vector2 p = Player.transform.position;
            if (!Won && Player.Grounded && p.x>24 && p.x<32 && Checkpoint<1) SetCheckpoint(1);
            if (!Won && Player.Grounded && p.x>49 && p.x<55 && Checkpoint<2) SetCheckpoint(2);
            if (!FrameBroken && p.x>71 && p.x<74 && p.y>0.4f && p.y<4.5f && Player.Velocity.x>12) BreakFrame();
            if (!Won && p.x>FinishX && p.y>0 && p.y<6) Win();
            if (Player.Grounded && !lastGrounded && Player.Velocity.y<2) { Play(landSound); jumpVisual=0.15f; }
            lastGrounded=Player.Grounded;
            jumpVisual=Mathf.Max(0,jumpVisual-Time.deltaTime);
            for(int i=pops.Count-1;i>=0;i--) if(Time.time>pops[i].end) pops.RemoveAt(i);
            for(int i=shards.Count-1;i>=0;i--)
            {
                var s=shards[i];
                if(Time.time>s.end) { if(s.t) Destroy(s.t.gameObject); shards.RemoveAt(i); continue; }
                s.velocity += Vector3.down*13*Time.deltaTime;
                s.t.position += s.velocity*Time.deltaTime;
                s.t.Rotate(0,0,s.spin*Time.deltaTime);
            }
        }

        void LateUpdate()
        {
            Vector3 p = Player.transform.position;
            float look = Mathf.Clamp(Player.Velocity.x*0.22f,-2,3.5f);
            cameraX = Mathf.Lerp(cameraX,Mathf.Max(-1,p.x+look),1-Mathf.Exp(-5*Time.deltaTime));
            cameraY = Mathf.Lerp(cameraY,Mathf.Clamp(p.y+1.9f,4.3f,10),1-Mathf.Exp(-3*Time.deltaTime));
            MainCamera.transform.position = new Vector3(cameraX,cameraY+3,-26);
            // Fixed camera orientation; only follows in X/Y.
            float speed=Player.Velocity.magnitude;
            MainCamera.orthographicSize=Mathf.Lerp(MainCamera.orthographicSize,7.4f+Mathf.Clamp01((speed-10)/16)*1.3f,Time.deltaTime*2);
            rope.enabled=Player.Attached;
            if(Player.Attached) { rope.SetPosition(0,p+new Vector3(0.12f,0.35f,-0.3f)); rope.SetPosition(1,Player.Anchor.position); }
            trail.emitting=speed>12 && !Won;
            float run=Time.time*18;
            float tilt=Player.Attached?Mathf.Clamp(-Player.Velocity.x*1.8f,-35,35):Player.Grounded?-Player.Velocity.x*1.2f: -Player.Velocity.x*0.8f;
            visual.localRotation=Quaternion.Euler(0,0,tilt);
            float f=Player.Facing;
            visual.localScale=new Vector3(f,1-jumpVisual*0.6f,1);
            armL.localRotation=Quaternion.Euler(0,0,Player.Attached?-145:Mathf.Sin(run)*35*Mathf.Clamp01(speed/8));
            armR.localRotation=Quaternion.Euler(0,0,Player.Attached?145:-Mathf.Sin(run)*35*Mathf.Clamp01(speed/8));
            legL.localRotation=Quaternion.Euler(0,0,Player.Grounded?Mathf.Sin(run)*32*Mathf.Clamp01(speed/8):28);
            legR.localRotation=Quaternion.Euler(0,0,Player.Grounded?-Mathf.Sin(run)*32*Mathf.Clamp01(speed/8):-35);
        }

        public Transform PickAnchor(bool mouseAim)
        {
            Transform best=null; float score=float.PositiveInfinity;
            Vector2 p=Player.transform.position;
            Vector3 mouseWorld=Vector3.zero;
            if(mouseAim)
            {
                var ray=MainCamera.ScreenPointToRay(Input.mousePosition);
                var plane=new Plane(Vector3.forward,Vector3.zero);
                if(plane.Raycast(ray,out float enter)) mouseWorld=ray.GetPoint(enter);
            }
            foreach(var a in Anchors)
            {
                float d=Vector2.Distance(p,a.position);
                if(d>RooftopMotor.HookRange || a.position.y<p.y-0.5f) continue;
                if(Physics2D.Linecast(p+Vector2.up*0.2f,a.position,1<<8)) continue;
                float s=mouseAim ? Vector2.Distance(mouseWorld,a.position) : d+(a.position.x<p.x-1?8:0);
                if(s<score) { score=s; best=a; }
            }
            return best;
        }

        void SetCheckpoint(int n) { Checkpoint=n; Burst(Player.transform.position+Vector3.up,"SAVED!",Cyan); Notify("CHECKPOINT "+n+" / LANDING SAVED",2); }
        public void Respawn(bool failed)
        {
            if(failed) { Deaths++; flashUntil=Time.time+0.22f; }
            Player.Warp(SpawnPoints[Checkpoint]);
            Won=false; ResetCount++;
            trail.Clear();
            cameraX=SpawnPoints[Checkpoint].x+1;
            cameraY=4.3f;
            Notify(failed?"NEW PANEL. TRY AGAIN.":"CHECKPOINT RESTART",1.7f);
        }
        public void RestartRun()
        {
            Checkpoint=0; Deaths=0; RunTime=0; bestX=-3; Won=false;
            FrameBroken=false; if(gate) gate.gameObject.SetActive(true);
            Respawn(false);
        }
        void Win()
        {
            Won=true; Player.Release(); Player.Locked=true;
            Burst(Player.transform.position+Vector3.up*2,"TO BE CONTINUED!",Pink);
            Notify("ISSUE COMPLETE",4); Play(winSound);
        }
        void BreakFrame()
        {
            FrameBroken=true; gate.gameObject.SetActive(false); frameBurstTime=Time.time;
            Burst(new Vector3(72,3,0),"KRAK!",Pink);
            for(int i=0;i<18;i++)
            {
                var piece=Shape("Broken panel ink",PrimitiveType.Cube,new Vector3(72,2.2f,0),new Vector3(0.12f,0.4f+i%3*0.15f,0.07f),i%3==0?pinkMat:inkMat);
                float a=i*2.39996f;
                shards.Add(new Shard {t=piece.transform,velocity=new Vector3(Mathf.Cos(a)*7+6,Mathf.Sin(a)*7,0),spin=170+i*15,end=Time.time+1.5f});
            }
        }
        public void Notify(string text,float seconds) { notification=text; notificationUntil=Time.time+seconds; }
        public void Burst(Vector3 at,string text,Color color)
        { pops.Add(new Pop{position=at,text=text,color=color,end=Time.time+0.65f}); if(text=="THWIP!"||text=="ZIP!") Play(zipSound); }
        TextMesh WorldText(string text,Vector3 p,float size,Color color)
        {
            var go=new GameObject(text); go.transform.SetParent(transform,false); go.transform.position=p;
            var tm=go.AddComponent<TextMesh>(); tm.text=text; tm.fontSize=64; tm.characterSize=size*0.12f; tm.color=color;
            tm.fontStyle=FontStyle.Bold; tm.anchor=TextAnchor.MiddleLeft;
            return tm;
        }

        AudioClip Tone(float hz,float length,float bend)
        {
            int rate=22050,n=(int)(rate*length); float[] data=new float[n];
            for(int i=0;i<n;i++) { float t=(float)i/n; data[i]=Mathf.Sin(2*Mathf.PI*hz*(1+bend*t)*i/rate)*Mathf.Pow(1-t,2)*0.4f; }
            var clip=AudioClip.Create("Original synthetic cue",n,1,rate,false); clip.SetData(data,0); return clip;
        }
        void Play(AudioClip clip) { if(speaker && clip) speaker.PlayOneShot(clip); }

        void InitGUI()
        {
            if(white) return;
            white=Texture2D.whiteTexture;
            title=new GUIStyle(GUI.skin.label){fontSize=24,fontStyle=FontStyle.Bold}; title.normal.textColor=Ink;
            small=new GUIStyle(GUI.skin.label){fontSize=13,fontStyle=FontStyle.Bold}; small.normal.textColor=Ink;
            label=new GUIStyle(title){fontSize=16};
            huge=new GUIStyle(title){fontSize=44,alignment=TextAnchor.MiddleCenter};
        }
        void RectFill(Rect r,Color c) { GUI.color=c; GUI.DrawTexture(r,white); GUI.color=Color.white; }
        void OnGUI()
        {
            if(Player==null || MainCamera==null) return;
            InitGUI();
            float sx=Screen.width/1440f,sy=Screen.height/900f;
            GUI.matrix=Matrix4x4.Scale(new Vector3(sx,sy,1));
            RectFill(new Rect(0,0,1440,9),Ink); RectFill(new Rect(0,891,1440,9),Ink);
            RectFill(new Rect(0,0,9,900),Ink); RectFill(new Rect(1431,0,9,900),Ink);
            RectFill(new Rect(26,25,348,86),Paper); RectFill(new Rect(26,25,6,86),Pink);
            GUI.Label(new Rect(46,36,330,35),"INKLINE / ROOFTOPS",title);
            GUI.Label(new Rect(47,76,320,24),"ISSUE 01     •     AN ORIGINAL COMIC RUN",small);
            RectFill(new Rect(1080,25,332,86),Ink);
            var st=new GUIStyle(small); st.normal.textColor=Paper;
            GUI.Label(new Rect(1098,37,290,24),"PANEL "+(Checkpoint+1)+" / 3     RETRIES "+Deaths,st);
            GUI.Label(new Rect(1098,66,290,24),RunTime.ToString("00.0")+" SEC     "+Player.Velocity.magnitude.ToString("0.0")+" M/S",st);
            RectFill(new Rect(460,32,515,6),new Color(Ink.r,Ink.g,Ink.b,0.18f));
            RectFill(new Rect(460,32,515*Mathf.Clamp01((bestX+3)/(FinishX+3)),6),Pink);
            GUI.Label(new Rect(460,44,540,23),"START     /     RELAY     /     BILLBOARD     /     FINISH",small);
            RectFill(new Rect(26,797,875,76),Paper);
            GUI.Label(new Rect(43,807,850,24),"A D  MOVE     SPACE  JUMP     E  HOOK / RELEASE     W S  REEL",label);
            GUI.Label(new Rect(43,838,850,24),"HOLD LEFT MOUSE  aim + web     Q  release     R  new run     BACKSPACE  checkpoint",small);
            RectFill(new Rect(1080,797,332,76),Player.Attached?Cyan:Paper);
            GUI.Label(new Rect(1097,808,302,26),Won?"ISSUE COMPLETE":Player.Attached?"WEB ATTACHED / "+Player.RopeLength.ToString("0.0")+" M":Player.Grounded?"ON THE ROOF":"IN THE AIR",label);
            GUI.Label(new Rect(1097,841,302,23),"F2  SAVE SCREENSHOT",small);
            if(Time.time<notificationUntil)
            {
                RectFill(new Rect(430,112,580,37),Ink);
                var n=new GUIStyle(label){alignment=TextAnchor.MiddleCenter}; n.normal.textColor=Paper;
                GUI.Label(new Rect(430,116,580,30),notification,n);
            }
            Transform target=PickAnchor(false);
            foreach(var a in Anchors)
            {
                Vector3 screen=MainCamera.WorldToScreenPoint(a.position);
                if(screen.z<0) continue;
                float x=screen.x/sx,y=(Screen.height-screen.y)/sy;
                if(x<12||x>1420||y<160||y>760) continue;
                if(a==target && !Player.Attached) { RectFill(new Rect(x-43,y+27,86,25),Cyan); GUI.Label(new Rect(x-39,y+29,90,24),"E / THWIP",small); }
            }
            foreach(var pop in pops)
            {
                Vector3 screen=MainCamera.WorldToScreenPoint(pop.position);
                float t=Mathf.Clamp01((pop.end-Time.time)/0.65f);
                var ps=new GUIStyle(huge){fontSize=30}; ps.normal.textColor=pop.color;
                float x=screen.x/sx,y=(Screen.height-screen.y)/sy-(1-t)*55;
                RectFill(new Rect(x-110,y-19,220,44),Ink);
                GUI.Label(new Rect(x-110,y-20,220,48),pop.text,ps);
            }
            if(Won)
            {
                RectFill(new Rect(405,292,630,262),Ink);
                var h=new GUIStyle(huge); h.normal.textColor=Paper;
                GUI.Label(new Rect(425,314,590,64),"ISSUE COMPLETE!",h);
                var s=new GUIStyle(label){alignment=TextAnchor.MiddleCenter}; s.normal.textColor=Cyan;
                GUI.Label(new Rect(425,393,590,42),RunTime.ToString("0.0")+" SEC   /   "+Deaths+" RETRIES   /   "+(FrameBroken?"FRAME SHATTERED":"FRAME INTACT"),s);
                s.normal.textColor=Paper; GUI.Label(new Rect(425,469,590,40),"PRESS R TO RUN ANOTHER ISSUE",s);
            }
            if(Time.time<flashUntil) RectFill(new Rect(9,9,1422,882),new Color(1,0.1f,0.4f,0.16f));
        }

        void OnDestroy()
        {
            foreach(var m in mats) if(m) Destroy(m);
            if(zipSound) Destroy(zipSound); if(landSound) Destroy(landSound); if(winSound) Destroy(winSound);
            if(Instance==this) Instance=null;
        }
    }
}
