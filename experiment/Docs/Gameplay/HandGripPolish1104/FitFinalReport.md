# Hand grip geometry fit

Selected diagnostic pose and attachment: **FitCandidateB.json**. The root agent owns the runtime `FitCandidate.json` schema. Do not use the discarded B2 axial slide or C pose.

- Preserve the original skeleton, skin weights, bind pose, D body motion, and wrist motion.
- The actual native hand closes around its local X direction. The previous attachment pointed almost along the palm normal and therefore pierced the palm.
- B uses a forward grip, with the tip toward the thumb side. The hand-local Blender shaft is normalized `(1, 0.2, -0.25)`; this is approximately 17.75 degrees from +X. The cutting edge faces the knuckle side.
- B attachment in UE units: position `[0, -0.048, 0.046]`, quaternion XYZW `[0.6024533510, 0.5060608387, 0.3855701685, 0.4819627404]`, scale `[0.01, 0.01, 0.01]`. The unusual position and scale reflect the native UE bone scale of 100.
- Finger rotations are absolute UE local rotations in the JSON. The three index-chain Blender pose curls are 60/100/75 degrees; the thumb uses the prior idle closure. Apply the same fixed grip layer to all six clips to avoid opening or changing grip between states.

## Evidence

`Geometry_D_Oblique.png` and the parent's actual UE Before captures agree on the original palm penetration. `Geometry_FitB_Side.png` and `Geometry_FitB_Oblique.png` show the fitted fingers around the handle. Root separately reviewed actual UE B images.

The hand crop uses the actual NativeMesh.fbx weighted geometry, posed from exported UE local/world transforms. It contains 5,832 vertices, taken from the original 186,599-vertex Blender body. Pose conversion uses the UE current/reference delta rather than guessing source animation axes. No source mesh, weights, rest transforms, or UE assets were changed by this diagnostic task.

## Contact measurements and remaining weapon detail

At nine samples across the central hand width, B gives approximately 11–15 mm of centerline-to-skin clearance. The real handle and winding radius is around 8–11.5 mm. This supports the visible central grip but is not a proof of no collision throughout every weapon component.

Closest-triangle signed normals alone misclassify some folded finger surfaces. Suspected penetrating samples were therefore checked with five forward ray-parity directions; at least four agreeing rays were required for the reported inside count. The cut hand mesh is not an ideal closed collision solid, so actual multi-angle UE review remains necessary.

The partial handle test (source |Z| < 5 cm) found 204 confirmed samples at the thumb-side collar and initially underestimated the full collar. The final test uses all 384 vertices of component `22 Guard ferrule`: at its original position, 145 vertices are inside the posed hand (maximum sampled depth about 9.76 mm). Moving this component +1.5 cm along sword Z does not clear it. A +3.0 cm component-only shift produces zero confirmed inside vertices in this test; see `FitCollarSweepReport.json`. The collar should be adjusted only on the enemy weapon derivative, with visual review for its relation to the guard plate. Moving the entire sword 12 mm along the shaft worsens the thumb collision and was rejected.

Component `29 Spirit jade sweep beneath grip` also crosses the finger backs in B. The separate hilt agent owns its enemy-only geometry adjustment. All player/source weapon geometry remains outside this diagnostic task's write scope.

Final acceptance must use the enemy-only hilt derivative and the B pose in the actual engine. These offline files are geometry evidence, not a claim that gameplay or every weapon triangle has already passed runtime validation.

## Final enemy derivative verification

Imported the actual exported `ArtSource/Weapons/Yueyao/EnemyGripPolish1104/YueyaoEnemyGrip.fbx` and rendered it with B in `Geometry_Final_Side.png` and `Geometry_Final_Oblique.png`. The decorative sweep visibly clears the finger backs. The collar change removes the deep thumb-side intrusion. On the central handle/winding subset (source |Z| < 5 cm), 46,767 vertices were checked; the conservative parity test still flags 159 vertices with maximum sampled depth 1.87 mm, down from the original collar's 9.76 mm full-component depth. Thus this is a visually fitted grip with small contact overlaps, not a mathematical zero-intersection claim. See `FitClearanceFitBFinalReport.json`.
