using UnityEngine;

namespace Inkline
{
    /// <summary>XY physics, Z depth is visual only. Input is sampled in Update and consumed by FixedUpdate.</summary>
    [RequireComponent(typeof(Rigidbody2D), typeof(CapsuleCollider2D))]
    public sealed class RooftopMotor : MonoBehaviour
    {
        public Rigidbody2D Body { get; private set; }
        public bool Grounded { get; private set; }
        public bool Attached => joint != null && joint.enabled;
        public Transform Anchor { get; private set; }
        public int AttachCount { get; private set; }
        public int JumpCount { get; private set; }
        public float MaxSpeed { get; private set; }
        public float RopeLength => Attached ? joint.distance : 0;
        public Vector2 Velocity => Body.velocity;
        public float Facing { get; private set; } = 1;
        public bool ExternalInput;
        public bool Locked;
        public float MoveInput;
        public float ReelInput;
        public const float RunSpeed = 9.5f;
        public const float HookRange = 16f;

        DistanceJoint2D joint;
        CapsuleCollider2D capsule;
        float coyote, jumpBuffer;
        bool attachQueued, releaseQueued;
        Transform queuedTarget;
        readonly RaycastHit2D[] hits = new RaycastHit2D[8];
        ContactFilter2D groundFilter;

        void Awake()
        {
            Body = GetComponent<Rigidbody2D>();
            Body.gravityScale = 2.6f;
            Body.freezeRotation = true;
            Body.collisionDetectionMode = CollisionDetectionMode2D.Continuous;
            Body.interpolation = RigidbodyInterpolation2D.Interpolate;
            capsule = GetComponent<CapsuleCollider2D>();
            capsule.size = new Vector2(0.62f, 1.65f);
            capsule.direction = CapsuleDirection2D.Vertical;
            var pm = new PhysicsMaterial2D("Frictionless runner") { friction = 0, bounciness = 0 };
            capsule.sharedMaterial = pm;
            groundFilter = new ContactFilter2D { useLayerMask = true, layerMask = 1 << 8, useTriggers = false };
            joint = gameObject.AddComponent<DistanceJoint2D>();
            joint.enabled = false;
            joint.autoConfigureConnectedAnchor = false;
            joint.autoConfigureDistance = false;
            joint.maxDistanceOnly = true;
            joint.enableCollision = false;
        }

        void Update()
        {
            if (!ExternalInput && !Locked)
            {
                MoveInput = (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow) ? 1 : 0)
                          - (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow) ? 1 : 0);
                ReelInput = (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow) ? 1 : 0)
                          - (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow) ? 1 : 0);
                if (Input.GetKeyDown(KeyCode.Space)) QueueJump();
                if (Input.GetMouseButtonDown(0)) QueueAttach(InkGame.Instance.PickAnchor(true));
                if (Input.GetMouseButtonUp(0) || Input.GetKeyDown(KeyCode.Q)) QueueRelease();
                if (Input.GetKeyDown(KeyCode.E))
                {
                    if (Attached) QueueRelease();
                    else QueueAttach(InkGame.Instance.PickAnchor(false));
                }
            }
        }

        public void QueueJump() { jumpBuffer = 0.14f; }
        public void QueueAttach(Transform target) { attachQueued = true; queuedTarget = target; }
        public void QueueRelease() { releaseQueued = true; }

        void FixedUpdate()
        {
            Grounded = false;
            int count = capsule.Cast(Vector2.down, groundFilter, hits, 0.12f);
            for (int i = 0; i < count; i++) if (hits[i].normal.y > 0.55f && Body.velocity.y < 1.5f) Grounded = true;
            coyote = Grounded ? 0.13f : coyote - Time.fixedDeltaTime;
            jumpBuffer -= Time.fixedDeltaTime;
            if (Locked) { MoveInput = 0; ReelInput = 0; }
            if (releaseQueued) Release();
            releaseQueued = false;
            if (attachQueued && !Locked) Attach(queuedTarget);
            attachQueued = false;
            Vector2 v = Body.velocity;
            if (!Locked && jumpBuffer > 0 && coyote > 0)
            {
                v.y = 12.8f;
                coyote = 0;
                jumpBuffer = 0;
                Grounded = false;
                JumpCount++;
                InkGame.Instance.Burst(transform.position, "LEAP!", InkGame.Pink);
            }
            float input = Locked ? 0 : MoveInput;
            if (Mathf.Abs(input) > 0.01f) Facing = Mathf.Sign(input);
            if (Attached)
            {
                // Tangential push preserves the pendulum; no direct horizontal velocity assignment.
                Vector2 radius = Body.position - joint.connectedAnchor;
                Vector2 tangent = new Vector2(-radius.y, radius.x).normalized;
                if (tangent.x < 0) tangent = -tangent;
                v += tangent * input * 20f * Time.fixedDeltaTime;
                joint.distance = Mathf.Clamp(joint.distance - ReelInput * 4f * Time.fixedDeltaTime, 2.4f, HookRange);
                v *= 0.999f;
            }
            else if (Grounded)
                v.x = Mathf.MoveTowards(v.x, input * RunSpeed, (Mathf.Abs(input) > 0 ? 62 : 48) * Time.fixedDeltaTime);
            else
            {
                // Air steering adds acceleration while keeping release momentum.
                if (Mathf.Abs(input) > 0.01f && (Mathf.Abs(v.x) < 15f || Mathf.Sign(v.x) != Mathf.Sign(input)))
                    v.x += input * 15f * Time.fixedDeltaTime;
                v.x *= 0.999f;
            }
            v = Vector2.ClampMagnitude(v, 26f);
            v.y = Mathf.Max(v.y, -28f);
            Body.velocity = v;
            MaxSpeed = Mathf.Max(MaxSpeed, v.magnitude);
        }

        void Attach(Transform target)
        {
            if (target == null) { InkGame.Instance.Notify("NO HOOK IN RANGE", 1.0f); return; }
            float distance = Vector2.Distance(Body.position, target.position);
            if (distance > HookRange || target.position.y < transform.position.y - 0.5f) return;
            // Buildings block the web, so hooks cannot be used through a roof.
            if (Physics2D.Linecast(Body.position + Vector2.up * 0.2f, target.position, 1 << 8)) return;
            Anchor = target;
            joint.connectedAnchor = target.position;
            joint.distance = Mathf.Max(distance, 2.4f);
            joint.enabled = true;
            AttachCount++;
            InkGame.Instance.Burst(target.position, "THWIP!", InkGame.Cyan);
        }

        public void Release()
        {
            bool wasAttached = Attached;
            joint.enabled = false;
            Anchor = null;
            if (wasAttached) InkGame.Instance.Burst(transform.position, "ZIP!", InkGame.Pink);
        }

        public void Warp(Vector2 position)
        {
            Release();
            Body.position = position;
            transform.position = new Vector3(position.x, position.y, 0);
            Body.velocity = Vector2.zero;
            Body.angularVelocity = 0;
            coyote = jumpBuffer = 0;
            attachQueued = releaseQueued = false;
            MoveInput = ReelInput = 0;
            Locked = false;
        }
    }
}
