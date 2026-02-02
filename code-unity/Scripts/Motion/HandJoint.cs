using Oculus.Interaction.Input;
using System;
using UnityEngine;

namespace Oculus.Interaction
{
    /// <summary>
    /// Standalone MonoBehavior representation of a tracked hand joint within an <see cref="IHand"/>.
    /// This type is primarily used for detecting grabs and pinches, now extended to handle multiple joints.
    /// </summary>
    public class HandJoint : MonoBehaviour
    {
        [SerializeField, Interface(typeof(IHand))]
        private UnityEngine.Object _hand;

        public IHand Hand { get; private set; }

        //#region OVR Fields

        [SerializeField]
        private HandJointId[] _handJointIds; // Changed to an array to handle multiple HandJointIds


        //#endregion OVR Fields

        //#region OpenXR Fields

        [SerializeField]
        [InspectorName("Offset")]
        private Vector3 _posOffset;

        [SerializeField]
        [InspectorName("Rotation")]
        private Quaternion _rotOffset = Quaternion.identity;

        [Tooltip("Provided for backwards compatibility. When set, the rotation of the driven " +
            "transform for this component will match the legacy hand skeleton joint orientation " +
            "rather than the current OpenXR joint orientation.")]
        [SerializeField]
        private bool _useLegacyOrientation = false;

        //#endregion OpenXR Fields

#if ISDK_OPENXR_HAND
        [Obsolete("This property is provided for backwards compatibility only.")]
        public bool UseLegacyOrientation
        {
            get => _useLegacyOrientation;
            set => _useLegacyOrientation = value;
        }
#endif

        [SerializeField]
        private bool _mirrorOffsetsForLeftHand = true;

        #region OpenXR Fields

        [Header("Freeze rotations")]
        [SerializeField]
        private bool _freezeRotationX = false;

        [SerializeField]
        private bool _freezeRotationY = false;

        [SerializeField]
        private bool _freezeRotationZ = false;

        #endregion OpenXR Fields

#if ISDK_OPENXR_HAND
        public bool FreezeRotationX
        {
            get => _freezeRotationX;
            set => _freezeRotationX = value;
        }
        public bool FreezeRotationY
        {
            get => _freezeRotationY;
            set => _freezeRotationY = value;
        }
        public bool FreezeRotationZ
        {
            get => _freezeRotationZ;
            set => _freezeRotationZ = value;
        }
#endif

        public bool MirrorOffsetsForLeftHand
        {
            get => _mirrorOffsetsForLeftHand;
            set => _mirrorOffsetsForLeftHand = value;
        }

        #region Properties

        public HandJointId[] HandJointIds // Expose the array of joint IDs
        {
            get => _handJointIds;
            set => _handJointIds = value;
        }

        public Vector3 LocalPositionOffset
        {
            get => _posOffset;
            set => _posOffset = value;
        }

        public Quaternion RotationOffset
        {
            get => _rotOffset;
            set => _rotOffset = value;
        }

        #endregion

        private Pose _cachedPose = Pose.identity;

        protected bool _started = false;

        protected virtual void Awake()
        {
            Hand = _hand as IHand;
        }

        protected virtual void Start()
        {
            this.BeginStart(ref _started);
            this.AssertField(Hand, nameof(Hand));
            this.EndStart(ref _started);
        }

        protected virtual void OnEnable()
        {
            if (_started)
            {
                Hand.WhenHandUpdated += HandleHandUpdated;
            }
        }

        protected virtual void OnDisable()
        {
            if (_started)
            {
                Hand.WhenHandUpdated -= HandleHandUpdated;
            }
        }

        private void HandleHandUpdated()
        {
            // Iterate through each hand joint ID and apply the pose.
            foreach (var jointId in _handJointIds)
            {
                if (Hand.GetJointPose(jointId, out Pose pose))
                {
                    GetOffset(ref _cachedPose, Hand.Handedness, Hand.Scale);

#if ISDK_OPENXR_HAND
                    _cachedPose.Postmultiply(pose);
                    //if (UseLegacyOrientation)
                    //{
                    //    _cachedPose.rotation = pose.rotation *
                    //         (Hand.Handedness == Handedness.Left ?
                    //             Quaternion.Euler(LEFT_LEGACY_ROT) :
                    //             Quaternion.Euler(RIGHT_LEGACY_ROT));
                    //}
#else
                    _cachedPose.position = pose.position + RotationOffset * pose.rotation * _cachedPose.position;
                    _cachedPose.rotation = pose.rotation;
#endif

#if ISDK_OPENXR_HAND
                    _cachedPose.rotation = FreezeRotation(_cachedPose.rotation);
#endif

                    transform.SetPose(_cachedPose);
                }
            }
        }

#if ISDK_OPENXR_HAND
        private Quaternion FreezeRotation(Quaternion rotation)
        {
            if (_freezeRotationX || _freezeRotationY || _freezeRotationZ)
            {
                Vector3 eulerAngles = rotation.eulerAngles;
                Quaternion pitch = Quaternion.Euler(new Vector3(eulerAngles.x, 0.0f, 0.0f));
                Quaternion yaw = Quaternion.Euler(new Vector3(0.0f, eulerAngles.y, 0.0f));
                Quaternion roll = Quaternion.Euler(new Vector3(0.0f, 0.0f, eulerAngles.z));
                Quaternion finalSourceRotation = Quaternion.identity;

                if (!_freezeRotationY)
                {
                    finalSourceRotation *= yaw;
                }
                if (!_freezeRotationX)
                {
                    finalSourceRotation *= pitch;
                }
                if (!_freezeRotationZ)
                {
                    finalSourceRotation *= roll;
                }
                rotation = finalSourceRotation;
            }
            return rotation;
        }
#endif

        private void GetOffset(ref Pose pose, Handedness handedness, float scale)
        {
            if (_mirrorOffsetsForLeftHand && handedness == Handedness.Left)
            {
                pose.position = HandMirroring.Mirror(LocalPositionOffset * scale);
                pose.rotation = HandMirroring.Mirror(RotationOffset);
            }
            else
            {
                pose.position = LocalPositionOffset * scale;
                pose.rotation = RotationOffset;
            }
        }

        #region Inject

        public void InjectAllHandJoint(IHand hand)
        {
            InjectHand(hand);
        }

        public void InjectHand(IHand hand)
        {
            _hand = hand as UnityEngine.Object;
            Hand = hand;
        }

        #endregion;
    }
}
