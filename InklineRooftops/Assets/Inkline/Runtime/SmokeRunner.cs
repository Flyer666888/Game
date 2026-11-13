using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Inkline
{
    /// <summary>Only runs when explicitly requested by editor tool or --inkline-smoke.</summary>
    public sealed class SmokeRunner : MonoBehaviour
    {
        [Serializable] public class Result
        {
            public string utc, engine, status;
            public List<string> passed = new List<string>();
            public List<string> failed = new List<string>();
            public int hooks, resets;
            public float maximumSpeed;
        }
        public static bool Requested;
        public static bool Finished;
        public static Result Last;
        public static string OutputDirectory;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Launch()
        {
            bool command = Array.IndexOf(Environment.GetCommandLineArgs(), "--inkline-smoke") >= 0;
            if (Requested || command) new GameObject("Explicit smoke test runner").AddComponent<SmokeRunner>();
        }

        void Check(bool condition,string message)
        { if(condition) Last.passed.Add(message); else Last.failed.Add(message); }

        IEnumerator Start()
        {
            Finished=false;
            Last=new Result{utc=DateTime.UtcNow.ToString("o"),engine=Application.unityVersion,status="RUNNING"};
            yield return null;
            var game=InkGame.Instance;
            var p=game.Player;
            game.TestMode=true; p.ExternalInput=true;
            game.RestartRun();
            yield return new WaitForSeconds(0.6f);
            Check(p.Grounded,"Player settles on start roof");
            Vector2 start=p.Body.position;
            p.MoveInput=1;
            yield return new WaitForSeconds(0.4f);
            Check(p.Body.position.x>start.x+1,"Move input advances player");
            p.QueueJump();
            yield return new WaitForSeconds(0.25f);
            Check(p.Body.position.y>start.y+1,"Buffered jump leaves roof");
            p.QueueAttach(game.Anchors[0]);
            yield return new WaitForSeconds(0.08f);
            // At this point the hook may still be out of range; test at a controlled reachable pose.
            p.Warp(new Vector2(9,3)); p.MoveInput=1; p.QueueAttach(game.Anchors[0]);
            yield return new WaitForSeconds(0.12f);
            Check(p.Attached,"Fixed anchor creates distance joint");
            Vector2 before=p.Body.position;
            yield return new WaitForSeconds(0.6f);
            Check(Vector2.Distance(before,p.Body.position)>1,"Attached body swings under gravity and tangential input");
            float length=p.RopeLength;
            p.ReelInput=1;
            yield return new WaitForSeconds(0.3f);
            Check(p.RopeLength<length-0.5f,"Reel input shortens rope");
            p.ReelInput=0; p.QueueRelease();
            yield return new WaitForSeconds(0.05f);
            Check(!p.Attached && p.Velocity.magnitude>1,"Release keeps momentum");
            p.Warp(new Vector2(0,-9));
            yield return new WaitForSeconds(0.15f);
            Check(game.Deaths==1 && p.Body.position.y>0,"Falling resets to spawn");
            p.Warp(new Vector2(26,2));
            yield return new WaitForSeconds(0.7f);
            Check(game.Checkpoint==1,"Landing on relay activates checkpoint");
            p.Warp(new Vector2(40,-9));
            yield return new WaitForSeconds(0.2f);
            Check(Mathf.Abs(p.Body.position.x-25)<0.5f,"Failure returns to latest checkpoint");
            game.RestartRun();
            yield return new WaitForSeconds(0.4f);
            p.MoveInput=1;
            bool route=true;
            for(int gap=0;gap<3;gap++)
            {
                float edge=gap==0?8.5f:gap==1?31.5f:54.5f;
                float landing=gap==0?23:gap==1?47:70;
                float timeout=Time.time+8;
                while(p.Body.position.x<edge && Time.time<timeout) { p.MoveInput=1; yield return null; }
                if(Time.time>=timeout) { route=false; break; }
                p.QueueJump();
                yield return new WaitForSeconds(0.18f);
                p.QueueAttach(game.Anchors[gap]);
                yield return new WaitForSeconds(0.1f);
                if(!p.Attached) { route=false; break; }
                if(gap==0) Capture("01-swing.png");
                timeout=Time.time+4;
                while(p.Body.position.x<game.Anchors[gap].position.x+2.2f && Time.time<timeout) yield return null;
                p.QueueRelease();
                timeout=Time.time+5;
                while((p.Body.position.x<landing || !p.Grounded) && Time.time<timeout && game.Deaths==0) yield return null;
                if(game.Deaths>0 || Time.time>=timeout) { route=false; break; }
            }
            if(route)
            {
                float timeout=Time.time+5;
                while(!game.Won && Time.time<timeout) { p.MoveInput=1; yield return null; }
            }
            Check(route && game.Won,"Three consecutive swings and natural finish without teleporting");
            Capture("02-route-result.png");
            // Independent finish trigger test is explicitly controlled rather than claimed as traversal.
            p.Warp(new Vector2(77,2));
            yield return new WaitForSeconds(0.15f);
            Check(game.Won,"Finish trigger opens issue complete screen (controlled pose)");
            Capture("03-finish-trigger.png");
            Last.hooks=p.AttachCount; Last.resets=game.ResetCount; Last.maximumSpeed=p.MaxSpeed;
            Last.status=Last.failed.Count==0?"PASS":"FAIL";
            string dir=GetOutput(); Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir,"unity-smoke.json"),JsonUtility.ToJson(Last,true));
            Debug.Log("INKLINE_SMOKE "+Last.status+" "+Path.Combine(dir,"unity-smoke.json"));
            yield return new WaitForSeconds(0.5f);
            Finished=true;
            p.ExternalInput=false;
            Requested=false;
        }
        static string GetOutput()
        { return string.IsNullOrEmpty(OutputDirectory)?Path.Combine(Application.persistentDataPath,"Evidence"):OutputDirectory; }
        void Capture(string name)
        { Directory.CreateDirectory(GetOutput()); ScreenCapture.CaptureScreenshot(Path.Combine(GetOutput(),name)); }
    }
}
