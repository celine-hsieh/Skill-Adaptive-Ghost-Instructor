using System.Collections.Generic;
using UnityEngine;
using Oculus.Interaction.HandGrab.Visuals;
using Oculus.Interaction.Input;
using Oculus.Interaction.HandGrab;
using Oculus.Interaction.Editor;
using Oculus.Interaction;
using Oculus.Interaction.Utils;
using TMPro;

namespace Oculus.Interaction.Utils
{
    public class HandAnimationRecorderRuntime : MonoBehaviour
    {

        [SerializeField]
        private HandVisual _rightHandVisual;

        private HandGhostProvider _ghostProvider;

#if ISDK_OPENXR_HAND
        private HandGhostProvider _handGhostProvider;
        private HandGhostProvider GhostProvider => _handGhostProvider;
#else
        private HandGhostProvider GhostProvider => _ghostProvider;
#endif

        [SerializeField]
        private HandFingerJointFlags _includedJoints = HandFingerJointFlags.All;

        [SerializeField]
        private bool _includeJointPosition = false;

        [SerializeField]
        private string _folder = "HandMotionClips";
        [SerializeField]
        private string _clipName = "HandAnimation";

        [SerializeField]
        private int _framerate = 30;
        [SerializeField]
        private float _slopeRotationThreshold = 0.1f;
        [SerializeField]
        private float _slopePositionThreshold = 0.0005f;

        [SerializeField]
        private KeyCode _recordKey = KeyCode.Space;

        private JointRecord[] _rightJointRecords;
        private JointRecord _rightRootRecord;

        private float _startTime;
        public bool _isRecording;
        public TextMeshPro RecordText;

        [HideInInspector]
        public bool isMeasuring = false;
        [HideInInspector]
        public int userNumber;
        private bool prevIsMeasuring = false;


        private void Start()
        {
            if (_rightHandVisual == null)
                {
                Debug.LogError("HandVisual is not assigned.");
                enabled = false;
                return;
            }
        }

        private void Update()
        {
            if (UnityEngine.Input.GetKeyDown(_recordKey))
            {
                if (!_isRecording)
                {
                    StartRecording();
                }
                else
                {
                    StopRecording();
                }
            }
            if (isMeasuring && !prevIsMeasuring)
            {
                Debug.Log($"Start user hand animation recording: User{userNumber}");
                StartRecording();
            }

            if (!isMeasuring && prevIsMeasuring)
            {
                Debug.Log($"Stop and save user hand animation: User{userNumber}");
                StopRecording(true);
            }

            if (_isRecording)
            {
                HandleHandUpdated();
            }
            prevIsMeasuring = isMeasuring;
        }

        private void StartRecording()
        {
            if (_isRecording) return;

            _isRecording = true;
            _startTime = Time.time;

            if (_rightHandVisual != null)
                InitializeRecords(_rightHandVisual, out _rightJointRecords, out _rightRootRecord);
        }

        private void StopRecording(bool saveAsUserFormat = false)
        {
            if (!_isRecording) return;

            _isRecording = false;

            if (_rightHandVisual != null)
            {
                string clipName = saveAsUserFormat ? $"User{userNumber}_Right" : $"Right_{_clipName}";
                var rightClip = GenerateClipAsset(clipName, _rightRootRecord, _rightJointRecords, saveAsUserFormat);
                Debug.Log($"Right hand animation saved: Assets/{_folder}/Right_{_clipName}.anim");
            }
        }

        private void InitializeRecords(HandVisual visual, out JointRecord[] jointRecords, out JointRecord rootRecord)
        {
            jointRecords = new JointRecord[(int)HandJointId.HandEnd];
            Transform root = visual.Root;

            foreach (HandJointId jointId in IncludedJointIds())
            {
                Transform jointTransform = visual.GetTransformByHandJointId(jointId);
                string path = HandAnimationUtils.GetGameObjectPath(jointTransform, root);
                jointRecords[(int)jointId] = new JointRecord(jointId, path);
            }

            rootRecord = new JointRecord(HandJointId.Invalid, "");
        }

        private void HandleHandUpdated()
        {
            float time = Time.time - _startTime;

            if (_rightHandVisual != null)
                ReadPoses(_rightHandVisual, time, _rightRootRecord, _rightJointRecords);
        }

        private void ReadPoses(HandVisual visual, float time, JointRecord rootRecord, JointRecord[] jointRecords)
        {
            rootRecord.RecordPose(time, visual.Root.GetPose(Space.World));
            foreach (HandJointId jointId in IncludedJointIds())
            {
                Pose pose = visual.GetJointPose(jointId, Space.Self);
                jointRecords[(int)jointId].RecordPose(time, pose);
            }
        }

        private AnimationClip GenerateClipAsset(string title, JointRecord rootRecord, JointRecord[] jointRecords, bool saveAsUser)
        {
            AnimationClip clip = new AnimationClip
            {
                frameRate = _framerate
            };

            HandAnimationUtils.WriteAnimationCurves(ref clip, rootRecord, true);
            foreach (HandJointId jointId in IncludedJointIds())
            {
                int index = (int)jointId;
                HandAnimationUtils.WriteAnimationCurves(ref clip, jointRecords[index], _includeJointPosition);
            }
            HandAnimationUtils.Compress(ref clip, _slopeRotationThreshold, _slopePositionThreshold);

            string subFolder = saveAsUser ? "User" : "";
            string baseFolderPath = string.IsNullOrEmpty(subFolder) ? _folder : $"{_folder}/{subFolder}";
            string fullFolderPath = $"Assets/{baseFolderPath}";

            string versionedName = GetNextAvailableFileName(fullFolderPath, title, "anim");

            HandAnimationUtils.StoreAsset(clip, baseFolderPath, versionedName);
            return clip;
        }

        private string GetNextAvailableFileName(string folderPath, string baseName, string extension)
        {
#if UNITY_EDITOR
            if (!System.IO.Directory.Exists(folderPath))
            {
                System.IO.Directory.CreateDirectory(folderPath);
            }

            int version = 1;
            string fileName;
            string fullPath = "";

            do
            {
                fileName = $"{baseName}_v{version}.{extension}";
                fullPath = System.IO.Path.Combine(folderPath, fileName);
                version++;
            }
            while (System.IO.File.Exists(fullPath));

            return fileName;
#else
    return $"{baseName}_v1.{extension}";
#endif
        }


        private IEnumerable<HandJointId> IncludedJointIds()
        {
            for (HandJointId jointId = HandJointId.HandStart; jointId < HandJointId.HandEnd; jointId++)
            {
                int index = (int)jointId;
                if (((int)_includedJoints & (1 << index)) == 0)
                {
                    continue;
                }
                yield return jointId;
            }
        }

        public void WhenPress()
        {
            if (!_isRecording)
            {
                StartRecording();
                RecordText.text = "Stop Recording";
            }
                
            else
            {
                StopRecording();
                RecordText.text = "Start Recording";
            }
                
        }


    }
}
