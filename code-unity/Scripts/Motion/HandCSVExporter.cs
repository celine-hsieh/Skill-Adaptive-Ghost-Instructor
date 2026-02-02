// Assets/Editor/HandCSVExporter.cs
#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Collections.Generic;

public class HandCSVExporter : MonoBehaviour
{
    [Header("Rig & Joints (put the right hand Rig on this object; drag the joints to track)")]
    public Transform wrist;                    // use wrist for translation normalization
    public List<Transform> trackedJoints;      // output in order

    [Header("Sampling")]
    public float fps = 60f;

    [Header("Position Options")]
    public bool exportPosition = true;
    public bool useLocal = false;              // world or local (for position)
    public bool subtractWrist = true;          // translation normalization
    public bool scaleByHandSpan = false;       // scale normalization by wrist–middleTip length (optional)
    public Transform middleTip;                // if above is true, specify here

    public enum RotFormat { EulerDeg, Quaternion }
    public enum RotSpace  { Local, World }

    [Header("Rotation Options")]
    public bool exportRotation = true;
    public RotFormat rotationFormat = RotFormat.Quaternion;
    public RotSpace  rotationSpace  = RotSpace.Local;

    [Header("Folders")]
    public string userClipsFolder = "./HandMotionClips/User";
    public string taskClipsFolder = "./HandMotionClips/Task";
    public string outFolder       = "./HandMotionClips/Exports/HandCSV";

    // ==== UI ====
    [ContextMenu("Export All (Users + Task refs)")]
    public void ExportAll()
    {
        if (trackedJoints == null || trackedJoints.Count == 0)
        {
            Debug.LogError("Please drag the joints to track into trackedJoints.");
            return;
        }
        if (!exportPosition && !exportRotation)
        {
            Debug.LogError("Please select at least one output (Position or Rotation).");
            return;
        }

        Directory.CreateDirectory(outFolder);

        // first export reference (A/B)
        ExportClipByPath(Path.Combine(taskClipsFolder, "Right_HandAnimation_Melody_B.anim"), "Ref_Melody_B");
        ExportClipByPath(Path.Combine(taskClipsFolder, "Right_HandAnimation_Melody_A.anim"), "Ref_Melody_A");

        // batch export user clips
        string[] guids = AssetDatabase.FindAssets("t:AnimationClip", new[] { userClipsFolder });
        foreach (var guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
            if (clip == null) continue;

            var meta = ParseMetaFromName(Path.GetFileNameWithoutExtension(path));
            string baseName = $"{meta.user}_{meta.cond}_{meta.test}_{meta.trial}_{meta.melody}";
            ExportClip(clip, baseName);
        }

        AssetDatabase.Refresh();
        Debug.Log("HandCSVExporter: Export completed.");
    }

    void ExportClipByPath(string clipPath, string baseName)
    {
        var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
        if (clip == null)
        {
            Debug.LogWarning($"Reference animation not found: {clipPath}");
            return;
        }
        ExportClip(clip, baseName);
    }

    void ExportClip(AnimationClip clip, string baseName)
    {
        // 1) use wrist's Root as the animation root
        var srcRoot = wrist != null ? wrist.root : transform;

        // 2) generate a copy of the whole Rig (ensure the same path)
        var instRoot = Instantiate(srcRoot.gameObject);
        instRoot.hideFlags = HideFlags.HideAndDontSave;

        // 3) use Transform Path to re-grab the corresponding bones on the "copy"
        //    (avoid still pointing to the original scene object)
        string WristPathFromRoot = AnimationUtility.CalculateTransformPath(wrist, srcRoot);
        Transform instWrist = instRoot.transform.Find(WristPathFromRoot);

        var instJoints = new List<Transform>(trackedJoints.Count);
        foreach (var j in trackedJoints)
        {
            string path = AnimationUtility.CalculateTransformPath(j, srcRoot);
            var instJ = instRoot.transform.Find(path);
            if (instJ == null)
                Debug.LogWarning($"Cannot find path on the copy: {path}");
            instJoints.Add(instJ);
        }

        // 4) quick debug: count the number of paths that can be found on instRoot
        var binds = AnimationUtility.GetCurveBindings(clip);
        int resolved = 0;
        foreach (var b in binds)
            if (instRoot.transform.Find(b.path) != null) resolved++;
        if (resolved == 0)
            Debug.LogWarning($"This clip cannot find any binding on the copy, the values will not move: {clip.name}");

        // 5) sample
        AnimationMode.StartAnimationMode();
        float dt = 1f / Mathf.Max(1f, fps);
        int frames = Mathf.Max(1, Mathf.CeilToInt(clip.length / dt) + 1);

        var sb = new StringBuilder();
        sb.Append("time");
        foreach (var t in instJoints)
        {
            string n = Sanitize(t != null ? t.name : "NULL");
            if (exportPosition) sb.Append($",{n}_x,{n}_y,{n}_z");
            if (exportRotation)
            {
                if (rotationFormat == RotFormat.EulerDeg) sb.Append($",{n}_rx,{n}_ry,{n}_rz");
                else                                      sb.Append($",{n}_qx,{n}_qy,{n}_qz,{n}_qw");
            }
        }
        sb.AppendLine();

        for (int i = 0; i < frames; i++)
        {
            float tt = Mathf.Min(i * dt, Mathf.Max(0.0001f, clip.length));
            // important: sample on the "copy's root"
            AnimationMode.SampleAnimationClip(instRoot, clip, tt);

            Vector3 wristPosW = instWrist ? instWrist.position : Vector3.zero;
            Vector3 wristPosL = instWrist ? instWrist.localPosition : Vector3.zero;

            float scale = 1f;
            if (exportPosition && scaleByHandSpan && middleTip != null && instWrist != null)
            {
                // re-find middleTip on the copy
                string mtPath = AnimationUtility.CalculateTransformPath(middleTip, srcRoot);
                var instMT = instRoot.transform.Find(mtPath);
                if (instMT != null)
                {
                    var a = useLocal ? instWrist.localPosition : instWrist.position;
                    var b = useLocal ? instMT.localPosition   : instMT.position;
                    scale = Mathf.Max(1e-6f, Vector3.Distance(a, b));
                }
            }

            sb.Append(tt.ToString("F6"));
            foreach (var j in instJoints)
            {
                if (j == null)
                {
                    if (exportPosition) sb.Append(",0,0,0");
                    if (exportRotation)
                        sb.Append(rotationFormat == RotFormat.EulerDeg ? ",0,0,0" : ",0,0,0,1");
                    continue;
                }

                if (exportPosition)
                {
                    Vector3 p = useLocal ? j.localPosition : j.position;
                    if (subtractWrist && instWrist) p -= (useLocal ? wristPosL : wristPosW);
                    if (scaleByHandSpan) p /= scale;
                    sb.AppendFormat(",{0:F6},{1:F6},{2:F6}", p.x, p.y, p.z);
                }

                if (exportRotation)
                {
                    if (rotationFormat == RotFormat.EulerDeg)
                    {
                        Vector3 e = (rotationSpace == RotSpace.Local) ? j.localEulerAngles : j.rotation.eulerAngles;
                        sb.AppendFormat(",{0:F6},{1:F6},{2:F6}", e.x, e.y, e.z);
                    }
                    else
                    {
                        Quaternion q = (rotationSpace == RotSpace.Local) ? j.localRotation : j.rotation;
                        float inv = 1.0f / Mathf.Sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w);
                        sb.AppendFormat(",{0:F6},{1:F6},{2:F6},{3:F6}", q.x*inv, q.y*inv, q.z*inv, q.w*inv);
                    }
                }
            }
            sb.AppendLine();
        }

        AnimationMode.StopAnimationMode();
        DestroyImmediate(instRoot);

        string outPath = Path.Combine(outFolder, baseName + ".csv");
        File.WriteAllText(outPath, sb.ToString());
        Debug.Log($"Exported: {outPath}");
    }


    static string Sanitize(string n) => Regex.Replace(n, "[^A-Za-z0-9_]+", "_");

    struct Meta
    {
        public string user, cond, test, trial, melody;
    }

    Meta ParseMetaFromName(string name)
    {
        // e.g., User1_d1_B / User1_dR2_B / User7_s2_A ...
        var m = Regex.Match(name, @"^User(?<uid>\d+)_?(?<cond>[sd])(?<ret>R?)(?<trial>\d)_(?<mel>[A-Za-z])$",
                            RegexOptions.IgnoreCase);
        string uid     = m.Success ? m.Groups["uid"].Value : "X";
        string cond    = m.Success ? (m.Groups["cond"].Value.ToLower() == "d" ? "Dynamic" : "Static") : "NA";
        bool isRet     = m.Success && m.Groups["ret"].Value == "R";
        string test    = isRet ? "Retention" : "Immediate";
        string trial   = m.Success ? m.Groups["trial"].Value : "1";
        string melCode = m.Success ? m.Groups["mel"].Value.ToUpper() : "B";

        // A→C mapping
        // string mel = melCode == "A" ? "C" : melCode;

        return new Meta {
            user = "User" + uid, cond = cond, test = test, trial = "T" + trial, melody = "Melody_" + mel
        };
    }
}
#endif
