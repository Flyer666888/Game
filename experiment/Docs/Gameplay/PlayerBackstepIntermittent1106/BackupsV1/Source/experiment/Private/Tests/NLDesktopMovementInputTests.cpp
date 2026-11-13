#if WITH_DEV_AUTOMATION_TESTS

#include "Player/NLLevelCombatPlayer.h"
#include "Components/BoxComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerInput.h"
#include "GameFramework/WorldSettings.h"
#include "InputKeyEventArgs.h"
#include "InputCoreTypes.h"
#include "Misc/AutomationTest.h"

namespace NLDesktopMovementInputTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    /** Native level pawn and real input cache, without a viewport, XR, encounter,
     *  checkpoint or main run. Only input delivery and the absent key-up are fixtures. */
    struct FWorld
    {
        UWorld* World = nullptr;
        ANLLevelCombatCharacter* Player = nullptr;
        APlayerController* Controller = nullptr;
        ULocalPlayer* LocalPlayer = nullptr;
        UInputComponent* Bindings = nullptr;
        const uint64 SavedFrameCounter = GFrameCounter;

        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinDesktopInput_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();

            AActor* Floor = World->SpawnActor<AActor>();
            UBoxComponent* Surface = NewObject<UBoxComponent>(Floor);
            Floor->SetRootComponent(Surface);
            Floor->AddInstanceComponent(Surface);
            Surface->InitBoxExtent(FVector(2000, 2000, 10));
            Surface->SetCollisionObjectType(ECC_WorldStatic);
            Surface->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            Surface->SetCollisionResponseToAllChannels(ECR_Block);
            Surface->RegisterComponent();
            Surface->SetWorldLocation(FVector(0, 0, -10));

            FActorSpawnParameters Spawn;
            Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Player = World->SpawnActor<ANLLevelCombatCharacter>(FVector(0, 0, 91), FRotator::ZeroRotator, Spawn);
            Controller = World->SpawnActor<APlayerController>();
            if (!Player || !Controller) return;
            // UE 5.8 identifies an offline controller by its ULocalPlayer, not
            // merely NM_Standalone. Do not register this player with the editor's
            // viewport/GameInstance or open any production progression profile.
            LocalPlayer = NewObject<ULocalPlayer>(GEngine);
            Controller->PlayerInput = NewObject<UPlayerInput>(Controller);
            Controller->SetPlayer(LocalPlayer);
            Controller->Possess(Player);
            Controller->SetControlRotation(FRotator::ZeroRotator);
            // ProcessInputStack is called explicitly below; an unrelated editor's
            // hardware input must not leak into this isolated controller.
            Controller->SetActorTickEnabled(false);
            Bindings = NewObject<UInputComponent>(Player);
            Player->AddInstanceComponent(Bindings);
            Bindings->RegisterComponent();
            Player->SetupPlayerInputComponent(Bindings);

            Player->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
            Step(12);
        }

        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            GFrameCounter = SavedFrameCounter;
        }

        bool Ready() const
        {
            return World && World->GetBegunPlay() && Player && Player->HasActorBegunPlay()
                && Controller && Controller->GetPawn() == Player && Player->GetController() == Controller
                && LocalPlayer && Controller->GetLocalPlayer() == LocalPlayer
                && Controller->IsLocalController() && Controller->PlayerInput && Bindings;
        }

        FString ReadyDiagnostic() const
        {
            return FString::Printf(TEXT("world=%d begun=%d pawn=%d pawnBegun=%d controller=%d possessed=%d reverseLink=%d localPlayer=%d local=%d playerInput=%d bindings=%d"),
                World != nullptr, World && World->GetBegunPlay(), Player != nullptr,
                Player && Player->HasActorBegunPlay(), Controller != nullptr,
                Controller && Controller->GetPawn() == Player,
                Player && Player->GetController() == Controller,
                LocalPlayer && Controller && Controller->GetLocalPlayer() == LocalPlayer,
                Controller && Controller->IsLocalController(),
                Controller && Controller->PlayerInput != nullptr, Bindings ? Bindings->KeyBindings.Num() : 0);
        }

        void Step(int32 Frames)
        {
            for (int32 Index = 0; Index < Frames; ++Index)
            {
                ++GFrameCounter;
                World->Tick(LEVELTICK_All, 1.0f / 60.0f);
            }
        }

        void Press(FKey Key)
        {
            Controller->PlayerInput->InputKey(FInputKeyEventArgs::CreateSimulated(Key, IE_Pressed, 1.0f));
            // An empty component stack still updates the real key-state cache.
            // Actions are dispatched through their actual registered delegates below.
            const TArray<UInputComponent*> EmptyStack;
            Controller->PlayerInput->ProcessInputStack(EmptyStack, 1.0f / 60.0f, false);
        }

        bool ExecutePressedBinding(FKey Key)
        {
            for (const FInputKeyBinding& Binding : Bindings->KeyBindings)
                if (Binding.Chord.Key == Key && Binding.KeyEvent == IE_Pressed && Binding.KeyDelegate.IsBound())
                {
                    // GetDelegateForManualSet would replace the real binding.
                    // Execute preserves and invokes the production Tab/slash delegate.
                    Binding.KeyDelegate.Execute(Key);
                    return true;
                }
            return false;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLDesktopCursorReleaseMovementTest,
    "Nilin.Desktop.Input.CursorReleaseClearsBackwardMovement", NLDesktopMovementInputTests::Flags)
bool FNLDesktopCursorReleaseMovementTest::RunTest(const FString& Parameters)
{
    NLDesktopMovementInputTests::FWorld F;
    if (!TestTrue(FString::Printf(TEXT("Native level pawn, controller and input fixture are ready [%s]"), *F.ReadyDiagnostic()), F.Ready())) return false;
    F.Press(EKeys::S); // Deliberately no key-up: UI/focus change swallowed it.
    F.Step(12);
    TestTrue(TEXT("Real cached S drives backward walking before the transition"),
        F.Controller->IsInputKeyDown(EKeys::S) && F.Player->GetVelocity().X < -1.0);
    F.Player->AddMovementInput(-FVector::ForwardVector, 1.0f, true);
    TestFalse(TEXT("There is unconsumed movement input to clear"), F.Player->GetPendingMovementInputVector().IsNearlyZero());

    if (!TestTrue(TEXT("Actual Tab binding executes"), F.ExecutePressedBinding(EKeys::Tab))) return false;
    TestTrue(TEXT("Tab releases the cursor"), F.Controller->bShowMouseCursor);
    TestFalse(TEXT("Cursor release clears the missing-key-up S cache"), F.Controller->IsInputKeyDown(EKeys::S));
    TestTrue(TEXT("Cursor release cancels walking momentum immediately"), F.Player->GetVelocity().IsNearlyZero());
    TestTrue(TEXT("Cursor release consumes the queued movement vector"), F.Player->GetPendingMovementInputVector().IsNearlyZero());

    // OS events can continue arriving while the pointer is outside the playfield.
    // Such events must not move the pawn until the cursor is explicitly recaptured.
    F.Press(EKeys::S);
    const FVector ReleasedLocation = F.Player->GetActorLocation();
    F.Step(24);
    TestTrue(TEXT("Released-cursor key events cannot move the player"),
        F.Player->GetActorLocation().Equals(ReleasedLocation, .1));
    TestTrue(TEXT("Released cursor leaves no movement input queued"), F.Player->GetPendingMovementInputVector().IsNearlyZero());
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLDesktopCursorRecaptureMovementTest,
    "Nilin.Desktop.Input.RecaptureRearmsWalkingAndPreservesHeldMoveOnSlash", NLDesktopMovementInputTests::Flags)
bool FNLDesktopCursorRecaptureMovementTest::RunTest(const FString& Parameters)
{
    NLDesktopMovementInputTests::FWorld F;
    if (!TestTrue(FString::Printf(TEXT("Native level pawn, controller and input fixture are ready [%s]"), *F.ReadyDiagnostic()), F.Ready())) return false;
    if (!TestTrue(TEXT("Actual Tab release binding executes"), F.ExecutePressedBinding(EKeys::Tab))) return false;
    F.Press(EKeys::S);
    F.Player->AddMovementInput(-FVector::ForwardVector, 1.0f, true);
    F.Player->GetCharacterMovement()->Velocity = FVector(-150, 0, 0);
    if (!TestTrue(TEXT("Actual Tab recapture binding executes"), F.ExecutePressedBinding(EKeys::Tab))) return false;
    TestFalse(TEXT("Tab recaptures the cursor"), F.Controller->bShowMouseCursor);
    TestFalse(TEXT("Recapture discards S cached while the cursor was released"), F.Controller->IsInputKeyDown(EKeys::S));
    TestTrue(TEXT("Recapture clears queued movement"), F.Player->GetPendingMovementInputVector().IsNearlyZero());
    TestTrue(TEXT("Recapture clears old walking momentum"), F.Player->GetVelocity().IsNearlyZero());
    const FVector RecapturedLocation = F.Player->GetActorLocation();
    F.Step(12);
    TestTrue(TEXT("Recapture alone does not restart backward walking"),
        F.Player->GetActorLocation().Equals(RecapturedLocation, .1));

    F.Press(EKeys::W);
    F.Step(12);
    TestTrue(TEXT("A fresh W press resumes real forward walking"),
        F.Player->GetActorLocation().X > RecapturedLocation.X + 5.0 && F.Player->GetVelocity().X > 1.0);
    const FVector BeforeSlash = F.Player->GetActorLocation();
    const FTransform HandBeforeSlash = F.Player->RightHand->GetRelativeTransform();
    if (!TestTrue(TEXT("Actual left-mouse slash binding executes"), F.ExecutePressedBinding(EKeys::LeftMouseButton))) return false;
    F.Step(4);
    TestFalse(TEXT("Native slash animates the hand"), F.Player->RightHand->GetRelativeTransform().Equals(HandBeforeSlash, .01));
    TestTrue(TEXT("Slashing does not erase a valid held W press"), F.Controller->IsInputKeyDown(EKeys::W));
    TestTrue(TEXT("Intentional forward walking continues during the slash"),
        F.Player->GetActorLocation().X > BeforeSlash.X + 1.0 && F.Player->GetVelocity().X > 1.0);
    return !HasAnyErrors();
}

#endif
