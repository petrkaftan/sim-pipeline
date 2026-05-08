castellatedMesh true;
snap true;
addLayers false;

maxLocalCells 100000;
maxGlobalCells 2000000;
minRefinementCells 0;
maxLoadUnbalance 0.10;
nCellsBetweenLevels 2;

innerCylinderSurfaceRefinementLevel (3 3);
propellerTipSurfaceRefinementLevel (5 5);

outerCylinderRefinementRegionLevel ((1E15 2));
innerCylinderRefinementRegionMode distance;
innerCylinderRefinementRegionLevel ((0.005 3) (0.030 2));
propellerTipRefinementRegionMode distance;
propellerTipRefinementRegionLevel ((0.002 5) (0.01 4) (0.03 3));

nSmoothPatch 3;
tolerance 1.0;
nSolveIter 30;
nRelaxIter 20;
nFeatureSnapIter 10;
implicitFeatureSnap true;
explicitFeatureSnap true;
multiRegionFeatureSnap true;


relativeSizes false;
propellerTipSurfaceLayers 5;
expansionRatio 1.15;
firstLayerThickness 0.00006;
minThickness 0.000006;
nGrow 0;
featureAngle 180;
addLayersnRelaxIter 5;
nSmoothSurfaceNormals 1;
nSmoothNormals 3;
nSmoothThickness 20;
maxFaceThicknessRatio 2.0;
maxThicknessToMedialRatio 1.0;
minMedialAxisAngle 30;
nLayerIter 50;
nBufferCellsNoExtrude 0;

maxNonOrtho 65;
maxBoundarySkewness 4;
maxInternalSkewness 4;
maxConcave 80;
minVol 1e-13;
mergeTolerance 1e-6;
nSmoothScale 4;
