using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Inkline.Editor
{
    [InitializeOnLoad]
    public static class ProjectTools
    {
        const string ScenePath="Assets/Scenes/Rooftops.unity";
        static ProjectTools()
        {
            EditorApplication.delayCall += () =>
            {
                if(!File.Exists(ScenePath) && !EditorApplication.isPlayingOrWillChangePlaymode) Setup();
            };
        }

        [MenuItem("INKLINE/1 • Create or open rooftop scene")]
        public static void Setup()
        {
            if(!File.Exists(ScenePath))
            {
                Directory.CreateDirectory("Assets/Scenes");
                var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                new GameObject("INKLINE — game bootstrap").AddComponent<InkGame>();
                EditorSceneManager.SaveScene(scene,ScenePath);
            }
            else EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
            PlayerSettings.companyName="Original Prototype";
            PlayerSettings.productName="Inkline Rooftops";
            PlayerSettings.defaultScreenWidth=1440; PlayerSettings.defaultScreenHeight=900;
            PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
            PlayerSettings.runInBackground=true;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone,ScriptingImplementation.Mono2x);
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(ScenePath,true)};
            var tags=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers=tags.FindProperty("layers"); if(layers!=null && layers.arraySize>8) { layers.GetArrayElementAtIndex(8).stringValue="Roof"; tags.ApplyModifiedProperties(); }
            AssetDatabase.SaveAssets();
            Debug.Log("INKLINE_SETUP_OK "+Path.GetFullPath(ScenePath));
        }

        [MenuItem("INKLINE/2 • Play smoke test + screenshots")]
        public static void PlaySmoke()
        {
            Setup();
            EditorApplication.playModeStateChanged += OnPlayState;
            EditorApplication.EnterPlaymode();
        }
        static void OnPlayState(PlayModeStateChange state)
        {
            if(state==PlayModeStateChange.EnteredPlayMode)
            {
                SmokeRunner.OutputDirectory=Path.GetFullPath("../Evidence");
                if(UnityEngine.Object.FindObjectOfType<SmokeRunner>()==null)
                    new GameObject("Explicit editor smoke runner").AddComponent<SmokeRunner>();
                EditorApplication.update+=WatchSmoke;
            }
        }
        static void WatchSmoke()
        {
            if(!SmokeRunner.Finished) return;
            EditorApplication.update-=WatchSmoke;
            EditorApplication.playModeStateChanged-=OnPlayState;
            bool success=SmokeRunner.Last!=null && SmokeRunner.Last.failed.Count==0;
            EditorApplication.ExitPlaymode();
            if(Application.isBatchMode) EditorApplication.delayCall+=()=>EditorApplication.Exit(success?0:2);
        }

        [MenuItem("INKLINE/3 • Build Windows playable")]
        public static void BuildWindows()
        {
            Setup();
            Directory.CreateDirectory("Builds/Windows");
            BuildReport report=BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes=new[]{ScenePath},locationPathName="Builds/Windows/InklineRooftops.exe",
                target=BuildTarget.StandaloneWindows64,options=BuildOptions.None
            });
            if(report.summary.result!=BuildResult.Succeeded) throw new Exception("Build failed: "+report.summary.result);
            Debug.Log("INKLINE_BUILD_OK "+report.summary.totalSize+" bytes");
        }
    }
}
