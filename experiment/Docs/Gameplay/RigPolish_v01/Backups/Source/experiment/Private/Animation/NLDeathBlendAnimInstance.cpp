#include "Animation/NLDeathBlendAnimInstance.h"

#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"

namespace
{
    struct FNLDeathBlendAnimInstanceProxy final : public FAnimSingleNodeInstanceProxy
    {
        explicit FNLDeathBlendAnimInstanceProxy(UAnimInstance* Instance)
            : FAnimSingleNodeInstanceProxy(Instance)
        {
        }

        virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override
        {
            FAnimSingleNodeInstanceProxy::PreUpdate(Instance, DeltaSeconds);
            const UNLDeathBlendAnimInstance* DeathInstance = Cast<UNLDeathBlendAnimInstance>(Instance);
            BlendAlpha = DeathInstance ? DeathInstance->GetBlendAlphaGameThread() : 1.0f;
            StartSnapshot = DeathInstance ? DeathInstance->GetStartSnapshot() : FPoseSnapshot();
            MeshBoneToSnapshot.Reset();

            // Copy and map on the game thread; evaluation only reads proxy-owned values.
            if (StartSnapshot.bIsValid && BlendAlpha < 1.0f)
            {
                const USkeletalMeshComponent* Mesh = Instance->GetSkelMeshComponent();
                const USkeletalMesh* MeshAsset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
                if (MeshAsset)
                {
                    const FReferenceSkeleton& ReferenceSkeleton = MeshAsset->GetRefSkeleton();
                    MeshBoneToSnapshot.Reserve(ReferenceSkeleton.GetNum());
                    for (int32 BoneIndex = 0; BoneIndex < ReferenceSkeleton.GetNum(); ++BoneIndex)
                    {
                        MeshBoneToSnapshot.Add(StartSnapshot.BoneNames.IndexOfByKey(
                            ReferenceSkeleton.GetBoneName(BoneIndex)));
                    }
                }
            }
        }

        virtual bool Evaluate(FPoseContext& Output) override
        {
            const bool bEvaluated = FAnimSingleNodeInstanceProxy::Evaluate(Output);
            if (!bEvaluated || !StartSnapshot.bIsValid || BlendAlpha >= 1.0f)
            {
                return bEvaluated;
            }

            const FBoneContainer& Bones = Output.Pose.GetBoneContainer();
            for (FCompactPoseBoneIndex PoseBoneIndex : Output.Pose.ForEachBoneIndex())
            {
                const int32 MeshBoneIndex = Bones.MakeMeshPoseIndex(PoseBoneIndex).GetInt();
                if (!MeshBoneToSnapshot.IsValidIndex(MeshBoneIndex)) continue;
                const int32 SnapshotIndex = MeshBoneToSnapshot[MeshBoneIndex];
                if (!StartSnapshot.LocalTransforms.IsValidIndex(SnapshotIndex)) continue;

                const FTransform DeathPose = Output.Pose[PoseBoneIndex];
                Output.Pose[PoseBoneIndex].Blend(
                    StartSnapshot.LocalTransforms[SnapshotIndex], DeathPose, BlendAlpha);
                Output.Pose[PoseBoneIndex].NormalizeRotation();
            }
            return bEvaluated;
        }

    private:
        FPoseSnapshot StartSnapshot;
        TArray<int32> MeshBoneToSnapshot;
        float BlendAlpha = 1.0f;
    };
}

UNLDeathBlendAnimInstance::UNLDeathBlendAnimInstance(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
}

bool UNLDeathBlendAnimInstance::BeginOnMesh(USkeletalMeshComponent* Mesh, float DurationSeconds)
{
    if (!CanSwitchAnimationInstance(Mesh) || !Mesh->GetWorld() || !Mesh->GetSkeletalMeshAsset()
        || Mesh->GetComponentSpaceTransforms().IsEmpty()) return false;

    FPoseSnapshot Snapshot;
    Mesh->SnapshotPose(Snapshot);
    if (!Snapshot.bIsValid || Snapshot.LocalTransforms.IsEmpty()
        || Snapshot.LocalTransforms.Num() != Snapshot.BoneNames.Num()) return false;
    for (const FTransform& Transform : Snapshot.LocalTransforms)
    {
        if (Transform.ContainsNaN()) return false;
    }

    Mesh->SetAnimInstanceClass(StaticClass());
    UNLDeathBlendAnimInstance* Instance = Cast<UNLDeathBlendAnimInstance>(Mesh->GetAnimInstance());
    if (!Instance) return false;

    Instance->StartSnapshot = MoveTemp(Snapshot);
    Instance->BlendStartGameTime = Mesh->GetWorld()->GetTimeSeconds();
    Instance->BlendDurationSeconds = FMath::Max(.01f, DurationSeconds);
    return true;
}

bool UNLDeathBlendAnimInstance::CanSwitchAnimationInstance(const USkeletalMeshComponent* Mesh)
{
    if (!Mesh || Mesh->IsPostEvaluatingAnimation()) return false;
#if DO_CHECK
    const UAnimInstance* Instance = Mesh->GetAnimInstance();
    if (Instance && (Instance->IsUpdatingAnimation() || Instance->IsPostUpdatingAnimation())) return false;
#endif
    return true;
}

float UNLDeathBlendAnimInstance::GetBlendAlphaGameThread() const
{
    const UWorld* World = GetWorld();
    if (!StartSnapshot.bIsValid || !World) return 1.0f;
    // World time freezes during pause; the captured pose and blend start stay unchanged.
    const float LinearAlpha = FMath::Clamp(
        static_cast<float>((World->GetTimeSeconds() - BlendStartGameTime) / BlendDurationSeconds), 0.0f, 1.0f);
    return LinearAlpha * LinearAlpha * (3.0f - 2.0f * LinearAlpha);
}

void UNLDeathBlendAnimInstance::ShiftBlendStartAfterPause(double PauseDurationSeconds)
{
    check(IsInGameThread());
    if (!StartSnapshot.bIsValid || !FMath::IsFinite(PauseDurationSeconds) || PauseDurationSeconds <= 0.0) return;
    BlendStartGameTime += PauseDurationSeconds;
}

FAnimInstanceProxy* UNLDeathBlendAnimInstance::CreateAnimInstanceProxy()
{
    return new FNLDeathBlendAnimInstanceProxy(this);
}

void UNLDeathBlendAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
    delete static_cast<FNLDeathBlendAnimInstanceProxy*>(InProxy);
}
