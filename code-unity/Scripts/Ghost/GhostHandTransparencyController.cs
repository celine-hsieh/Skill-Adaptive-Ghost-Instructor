using System.Collections.Generic;
using Unity.VisualScripting;
using UnityEngine;

[RequireComponent(typeof(Renderer))]
public class GhostHandTransparencyController : MonoBehaviour
{
    [Header("Transparency Control")]
    [Range(0.01f, 1.0f)] public float minAlpha = 0.1f;
    [Range(0.01f, 1.0f)] public float maxAlpha = 1.0f;

    [Header("Outline Settings")]
    [Range(0f, 1f)] public float minOutlineOpacity = 0.1f;
    [Range(0f, 1f)] public float maxOutlineOpacity = 1f;

    [Header("Test")]
    [Range(0f, 1f)]
    public float testTransparency = 0.7f;
    public bool testMode = true;

    public int windowSize = 5;
    private string opacityProperty = "_Opacity";
    private string outlineOpacityProperty = "_OutlineOpacity";
    private float targetAlpha = 0.5f;
    private float targetOutline = 0.5f;
    private float currentAlpha = 0.5f;
    private float currentOutline = 0.5f;
    public float lerpSpeed = 5f;

    public PianoGhostPlayer pianoGhostPlayer;
    private Renderer ghostRenderer;
    private MaterialPropertyBlock propBlock;
    private Queue<float> errorHistory = new Queue<float>();

    [HideInInspector]
    public float smoothedError = 0.5f;

    private float smoothingFast = 0.6f;  // Faster when becoming transparent
    private float smoothingSlow = 0.1f;  // Slower when becoming visible
    private float smoothedAlpha = 0.5f;


    [HideInInspector]
    public float lasttargetAlpha;

    void Awake()
    {
        ghostRenderer = GetComponent<Renderer>();
    }
    void Update()
    {
        if (!pianoGhostPlayer.isPlaying) return;
        else
        {
            if (testMode || !pianoGhostPlayer.isDynamicMode)
            {
                ghostRenderer.material.SetFloat(opacityProperty, testTransparency);
                ghostRenderer.material.SetFloat(outlineOpacityProperty, testTransparency);
            }
            else
            {
                currentAlpha = Mathf.Lerp(currentAlpha, targetAlpha, Time.deltaTime * lerpSpeed);
                currentOutline = Mathf.Lerp(currentOutline, targetOutline, Time.deltaTime * lerpSpeed);

                ghostRenderer.material.SetFloat(opacityProperty, currentAlpha);
                ghostRenderer.material.SetFloat(outlineOpacityProperty, currentOutline);
            }
        }
    }

    public void AddErrorRate(float errorRate)
    {
        if (pianoGhostPlayer.recentUserEvents.Count == 0)
        {
            targetAlpha = maxAlpha;
            lasttargetAlpha = maxAlpha;
            return;
        }

        // Keep errorRate in [0,1]
        errorRate = Mathf.Clamp01(errorRate);

        // Choose error‐smoothing: slow up, fast down
        float errorSmoothingUp = 0.2f;  // - When error jumps up, use a small weight (0.2)
        float errorSmoothingDown = 0.8f;  // - When error falls, use a large weight (0.8)
        float errorSmoothing = (errorRate > smoothedError)
                   ? errorSmoothingUp
                   : errorSmoothingDown;

        // Apply the chosen exponential‐moving‐average (EMA) smoothing:
        smoothedError = errorSmoothing * errorRate
                      + (1 - errorSmoothing) * smoothedError;

        // Emphasize low errors
        float curved = Mathf.Pow(smoothedError, 1.2f);

        // Map to raw alpha
        float rawAlpha = Mathf.Lerp(minAlpha, maxAlpha, curved);

        // Choose alpha‐smoothing: fast hide, slow show
        float smoothing = rawAlpha < smoothedAlpha ? smoothingFast : smoothingSlow;
        smoothedAlpha = smoothing * rawAlpha + (1f - smoothing) * smoothedAlpha;

        // Apply targets
        targetAlpha = smoothedAlpha;
        lasttargetAlpha = smoothedAlpha;

        targetOutline = Mathf.Lerp(minOutlineOpacity, maxOutlineOpacity, smoothedError);

        Debug.Log($"[GhostTransparency] err={errorRate:F2}, smErr={smoothedError:F2}, α={targetAlpha:F2}");
    }
}
