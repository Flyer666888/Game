#if WITH_DEV_AUTOMATION_TESTS

#include "Animation/NLDeathBlendAnimInstance.h"
#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyAnimationTransitionTest,
    "Nilin.EnemyAnimation.VisiblePoseTransition",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNLEnemyAnimationTransitionTest::RunTest(const FString& Parameters)
{
    if (!GEngine) return false;
    const uint64 SavedFrameCounter = GFrameCounter;
    const UWorld::InitializationValues Values = UWorld::InitializationValues()
        .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
        .ShouldSimulatePhysics(false).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game,false,
        FName(*FString::Printf(TEXT("NilinPoseTest_%s"),*FGuid::NewGuid().ToString(EGuidFormats::Digits))),
        nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!TestNotNull(TEXT("Isolated presentation world"),World)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    World->InitializeActorsForPlay(FURL());
    World->BeginPlay();
    if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();

    USkeletalMesh* Asset = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat.SK_WuxiaMale_Combat"));
    UAnimationAsset* Idle = LoadObject<UAnimationAsset>(nullptr,
        TEXT("/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Idle_Planted.Wuxia_Idle_Planted"));
    UAnimationAsset* Walk = LoadObject<UAnimationAsset>(nullptr,
        TEXT("/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Walk_Sword.Wuxia_Walk_Sword"));
    const bool bAssetsReady = TestNotNull(TEXT("Combat character mesh"),Asset)
        && TestNotNull(TEXT("Authored idle"),Idle) && TestNotNull(TEXT("Authored walk"),Walk);
    if (bAssetsReady)
    {
        AActor* Actor = World->SpawnActor<AActor>();
        USkeletalMeshComponent* Mesh = NewObject<USkeletalMeshComponent>(Actor);
        Actor->SetRootComponent(Mesh);
        Actor->AddInstanceComponent(Mesh);
        Mesh->SetSkeletalMeshAsset(Asset);
        Mesh->RegisterComponent();
        Mesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        Mesh->SetAnimation(Idle);
        Mesh->SetPosition(.4f,false);
        Mesh->Play(true);
        Mesh->TickAnimation(0,false);
        Mesh->RefreshBoneTransforms();
        FPoseSnapshot SourcePose;
        Mesh->SnapshotPose(SourcePose);
        TestTrue(TEXT("Source pose evaluated"),SourcePose.bIsValid && SourcePose.LocalTransforms.Num() > 20);
        if (TestTrue(TEXT("Start a safe visible-pose transition"),UNLDeathBlendAnimInstance::BeginOnMesh(Mesh,.16f)))
        {
            UNLDeathBlendAnimInstance* Blend = Cast<UNLDeathBlendAnimInstance>(Mesh->GetAnimInstance());
            Mesh->SetAnimation(Walk);
            Mesh->SetPosition(.4f,false);
            Mesh->Play(true);
            Mesh->TickAnimation(0,false);
            Mesh->RefreshBoneTransforms();
            FPoseSnapshot AtEntry;
            Mesh->SnapshotPose(AtEntry);
            bool bEntryContinuous = AtEntry.LocalTransforms.Num() == SourcePose.LocalTransforms.Num();
            for (int32 Index = 0; bEntryContinuous && Index < SourcePose.LocalTransforms.Num(); ++Index)
                bEntryContinuous = SourcePose.LocalTransforms[Index].Equals(AtEntry.LocalTransforms[Index],.001f);
            TestTrue(TEXT("Changing clip presents the previous pose at alpha zero, never reference pose"),bEntryContinuous);
            ++GFrameCounter;
            World->Tick(LEVELTICK_All,.08f);
            TestTrue(TEXT("The short transition progresses on game time"),
                Blend && FMath::IsNearlyEqual(Blend->GetBlendAlphaGameThread(),.5f,.03f));
            if (Blend)
            {
                Blend->ShiftBlendStartAfterPause(.08);
                TestTrue(TEXT("Local pause time does not advance the pose blend"),
                    FMath::IsNearlyZero(Blend->GetBlendAlphaGameThread(),.001f));
                TestTrue(TEXT("A second transition captures safely"),UNLDeathBlendAnimInstance::BeginOnMesh(Mesh,.12f));
                TestTrue(TEXT("Consecutive transitions preserve the animation instance"),Mesh->GetAnimInstance() == Blend);
            }
        }
    }
    World->EndPlay(EEndPlayReason::Quit);
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    GFrameCounter = SavedFrameCounter;
    return !HasAnyErrors();
}

#endif
