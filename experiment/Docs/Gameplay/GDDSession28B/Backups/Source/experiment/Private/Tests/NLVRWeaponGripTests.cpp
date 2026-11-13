#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLBladeComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "MotionControllerComponent.h"
#include "Player/NLVRPlayerCharacter.h"

namespace NLVRWeaponGripTests
{
    /** Loads the real player hand, grip animation and weapon through native BeginPlay.
     *  No GameInstance, encounter, save profile, HMD input or artificial attack is used. */
    class FScopedGripWorld
    {
    public:
        FScopedGripWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinVRGrip_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();

            FActorSpawnParameters Parameters;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Player = World->SpawnActor<ANLVRPlayerCharacter>(
                FVector(0.0, 0.0, 88.0), FRotator::ZeroRotator, Parameters);
            if (!Player) return;
            // Supplied tracked poses are test inputs. Never poll or synthesize an XR device.
            Player->SetActorTickEnabled(false);
            Player->LeftController->SetComponentTickEnabled(false);
            Player->RightController->SetComponentTickEnabled(false);
            EvaluateHand();
        }

        ~FScopedGripWorld()
        {
            if (!World) return;
            World->EndPlay(EEndPlayReason::Quit);
            if (GEngine) GEngine->DestroyWorldContext(World);
            World->DestroyWorld(false);
        }

        void EvaluateHand() const
        {
            Player->RightHand->TickAnimation(0.0f, false);
            Player->RightHand->RefreshBoneTransforms();
            Player->RightHand->UpdateComponentToWorld();
            Player->HeldWeapon->UpdateComponentToWorld();
        }

        UWorld* World = nullptr;
        ANLVRPlayerCharacter* Player = nullptr;
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRWeaponGripAxisTest,
    "Nilin.VR.WeaponGrip.AuthoredHandAndBladeFollowGripAxis",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNLVRWeaponGripAxisTest::RunTest(const FString& Parameters)
{
    using namespace NLVRWeaponGripTests;
    FScopedGripWorld Fixture;
    ANLVRPlayerCharacter* Player = Fixture.Player;
    if (!TestNotNull(TEXT("Native VR player spawned"), Player)) return false;
    if (!TestTrue(TEXT("Actual native BeginPlay completed"), Player->HasActorBegunPlay())) return false;
    if (!TestNotNull(TEXT("Actual equipped hand mesh loaded"), Player->RightHand->GetSkeletalMeshAsset())
        || !TestNotNull(TEXT("Actual grip animation evaluated"), Player->RightHand->GetAnimInstance())
        || !TestNotNull(TEXT("Actual equipped sword loaded"), Player->HeldWeapon->GetStaticMesh().Get())) return false;

    TestEqual(TEXT("Use the OpenXR grip pose explicitly"), Player->RightController->GetTrackingMotionSource(), FName(TEXT("RightGrip")));
    TestTrue(TEXT("Hand remains attached to the tracked grip"), Player->RightHand->GetAttachParent() == Player->RightController);
    TestTrue(TEXT("Sword remains attached to the hand, so both rotate together"), Player->HeldWeapon->GetAttachParent() == Player->RightHand);
    TestEqual(TEXT("Sword still uses the authored hand socket"), Player->HeldWeapon->GetAttachSocketName(), FName(TEXT("hand_r")));
    TestTrue(TEXT("Authored socket exists"), Player->RightHand->DoesSocketExist(TEXT("hand_r")));
    const FTransform WeaponInSocket = Player->HeldWeapon->GetRelativeTransform();
    const FTransform HandInGrip = Player->RightHand->GetRelativeTransform();

    // The standard OpenXR grip -Z (little finger -> thumb) is UE grip +X.
    // An upright physical handle therefore has UE grip +X pointing world +Z.
    const TArray<FRotator> GripRotations = {
        FRotator(90.0, 0.0, 0.0),
        FRotator(90.0, 130.0, 0.0),
        FRotator(90.0, 0.0, 75.0),
        FRotator(0.0, 0.0, 0.0),
        FRotator(0.0, 90.0, 0.0),
        FRotator(-90.0, 0.0, 0.0),
        FRotator(31.0, -43.0, 68.0)
    };
    for (int32 Index = 0; Index < GripRotations.Num(); ++Index)
    {
        const FRotator Rotation = GripRotations[Index];
        Player->RightController->SetWorldLocationAndRotation(FVector(40.0, 25.0, 120.0), Rotation);
        Fixture.EvaluateHand();
        const FTransform WeaponWorld = Player->HeldWeapon->GetComponentTransform();
        const FVector Root = WeaponWorld.TransformPosition(Player->Blade->BladeRootLocal);
        const FVector Middle = WeaponWorld.TransformPosition(Player->Blade->BladeMidLocal);
        const FVector Tip = WeaponWorld.TransformPosition(Player->Blade->BladeTipLocal);
        const FVector BladeDirection = (Tip - Root).GetSafeNormal();
        const FVector GripDirection = Player->RightController->GetForwardVector();
        TestTrue(*FString::Printf(TEXT("Pose %d: actual socket + weapon + combat samples follow the grip handle axis"), Index),
            FVector::DotProduct(BladeDirection, GripDirection) > 0.999);
        TestTrue(*FString::Printf(TEXT("Pose %d: blade middle stays on the same directed axis"), Index),
            FVector::DotProduct((Middle - Root).GetSafeNormal(), GripDirection) > 0.999);
        TestTrue(*FString::Printf(TEXT("Pose %d: blade length remains authored"), Index),
            FMath::IsNearlyEqual(FVector::Distance(Root, Tip),
                FVector::Distance(Player->Blade->BladeRootLocal, Player->Blade->BladeTipLocal), 0.01));
        TestTrue(*FString::Printf(TEXT("Pose %d: no hand/socket separation"), Index),
            Player->HeldWeapon->GetRelativeTransform().Equals(WeaponInSocket, 0.0001)
            && Player->RightHand->GetRelativeTransform().Equals(HandInGrip, 0.0001));
        if (Index == 0)
        {
            TestTrue(TEXT("Upright controller: actual blade tip points world up, never toward the wearer"),
                BladeDirection.Z > 0.999 && FMath::Abs(BladeDirection.X) < 0.001);
        }
        if (Index == 5)
        {
            TestTrue(TEXT("Turning the wrist downward turns the blade down; orientation is not locked to world up"),
                BladeDirection.Z < -0.999);
        }
    }
    return !HasAnyErrors();
}

#endif // WITH_DEV_AUTOMATION_TESTS
