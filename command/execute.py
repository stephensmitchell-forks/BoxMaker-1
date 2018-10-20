import math
import adsk.core
from . import value

# Event handler for the execute event.
class Handler( adsk.core.CommandEventHandler ):
    def __init__( self ):
        super().__init__()
    
    def CreateComponent( self, parent, name ):
        # Create Component
        identityTransform = adsk.core.Matrix3D.create()
        occurrence = parent.occurrences.addNewComponent( identityTransform )
        
        component = occurrence.component
        component.name = name
        
        return component
        
    def CalculateTabLength( self, length ):
        maxSize = 2
        tabCount = 1
        tabSize = maxSize + 1        
        
        while( tabSize > maxSize ):
            tabCount += 2
            tabSize = length / tabCount
            
        return tabCount, tabSize
    
    def CreateBase( self, parent, x, y, z ):
        
        component = self.CreateComponent( parent, "Base" )
        
        startPoint = adsk.core.Point3D.create( 0, 0, 0 )
        endPoint = adsk.core.Point3D.create( x, y, 0 )
        
        sketch = component.sketches.add( component.xZConstructionPlane )
        sketch.sketchCurves.sketchLines.addTwoPointRectangle( startPoint, endPoint )
        
        profile = sketch.profiles.item( 0 )
        
        # Create an extrusion input for the profile.
        features = component.features
        extrudes = features.extrudeFeatures
        extInput = extrudes.createInput( profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation )
        
        # Define that the extent of the extrusion is a distance extent of 5 cm.
        distance = adsk.core.ValueInput.createByReal( z )
        extInput.setDistanceExtent( False, distance )
        
        # Create the extrusion.
        extrudes.add( extInput )
        
        return component
        
    def CreateSide( self, parent, x, y, z ):
        
        component = self.CreateComponent( parent, "Side" )
        
        startPoint = adsk.core.Point3D.create( 0, 0, 0 )
        endPoint = adsk.core.Point3D.create( x, y, 0 )
        
        sketch = component.sketches.add( component.yZConstructionPlane )
        sketch.sketchCurves.sketchLines.addTwoPointRectangle( startPoint, endPoint )
        
        tabCount, tabLength = self.CalculateTabLength( x )
        
        centres = []
        
        tabX = 0
        for i in range( tabCount ):
            start = adsk.core.Point3D.create( tabX, 0, 0 )
            tabX += tabLength
            end = adsk.core.Point3D.create( tabX, z, 0 )
            sketch.sketchCurves.sketchLines.addTwoPointRectangle( start, end )
            
            centre = ( start.x + end.x ) / 2

            # We are only interested in extruding every other tab (so ignore evens)
            if i % 2 != 0:
                centres.append( centre )
        
        profiles = adsk.core.ObjectCollection.create()   

        tabMiddleY = z / 2

        for i in range( sketch.profiles.count ):
            profile = sketch.profiles.item( i )
            areaProperties = profile.areaProperties()
            middleX = areaProperties.centroid.x
            middleY = areaProperties.centroid.y
            
            if not math.isclose( middleY, tabMiddleY ):
                # Must be the rest of the side that isn't a tab
                profiles.add( profile )
            else:
                for centreX in centres:
                    # It matches a tab we want
                    if math.isclose( middleX, centreX ):
                        profiles.add( profile )
                        break
        
        # Create an extrusion input for the profile.
        features = component.features
        extrudes = features.extrudeFeatures
        extInput = extrudes.createInput( profiles, adsk.fusion.FeatureOperations.NewBodyFeatureOperation )
        
        # Define that the extent of the extrusion is a distance extent of 5 cm.
        distance = adsk.core.ValueInput.createByReal( z )
        extInput.setDistanceExtent( False, distance )
        
        # Create the extrusion.
        extrudes.add( extInput )
        
        return component

    def FindBRepCurvesOnAxis( self, component, axis ):

        edges = []
        
        for iB in range( component.bRepBodies.count ):
            body = component.bRepBodies.item( iB )
            
            for iE in range( body.edges.count ):
                edge = body.edges.item( iE )
                
                xIsClose = math.isclose( edge.startVertex.geometry.x, edge.endVertex.geometry.x )
                yIsClose = math.isclose( edge.startVertex.geometry.y, edge.endVertex.geometry.y )
                zIsClose = math.isclose( edge.startVertex.geometry.z, edge.endVertex.geometry.z )

                x = ( axis.x > 0 and not xIsClose ) or ( axis.x == 0 and xIsClose )
                y = ( axis.y > 0 and not yIsClose ) or ( axis.y == 0 and yIsClose )
                z = ( axis.z > 0 and not zIsClose ) or ( axis.z == 0 and zIsClose )
                
                if x and y and z:
                    edges.append( edge )

        return edges
        
    def CalcMidPoint( self, edge ):
        x = ( edge.startVertex.geometry.x + edge.endVertex.geometry.x ) / 2
        y = ( edge.startVertex.geometry.y + edge.endVertex.geometry.y ) / 2
        z = ( edge.startVertex.geometry.z + edge.endVertex.geometry.z ) / 2
        
        return x, y, z
        
    def AreMidPointsEqual( self, a, b ):
        midA = adsk.core.Point3D.create( *self.CalcMidPoint( a ) )
        midB = adsk.core.Point3D.create( *self.CalcMidPoint( b ) )
        
        return midA.isEqualTo( midB )
        
    def CalculateEdgeDirection( self, edge ):
        return edge.startVertex.geometry.vectorTo( edge.endVertex.geometry )
        
    def AreEdgesInTheSameDirection( self, a, b ):
        dirA = self.CalculateEdgeDirection( a )
        dirB = self.CalculateEdgeDirection( b )
        
        dirA.normalize()
        dirB.normalize()
        
        dp = dirA.dotProduct( dirB )
        
        return math.isclose( 1, dp )

    def VectorToString( self, vector ):
        return "X:{0} Y:{1} Z:{2}".format( vector.x, vector.y, vector.z )

    def EdgeToString( self, edge ):
        output  = "Start: " + self.VectorToString( edge.startVertex.geometry )
        output += "\n"
        output += "End  : " + self.VectorToString( edge.endVertex.geometry )
        
        return output

    def Join( self, root, componentA, componentB, axis, offset = 0 ):
        edgesA = self.FindBRepCurvesOnAxis( componentA, axis )
        edgesB = self.FindBRepCurvesOnAxis( componentB, axis )
        
        for edgeA in edgesA:
            for edgeB in edgesB:
                if self.AreMidPointsEqual( edgeA, edgeB ):
                    
                    joinA = adsk.fusion.JointGeometry.createByCurve( edgeA, adsk.fusion.JointKeyPointTypes.MiddleKeyPoint )
                    joinB = adsk.fusion.JointGeometry.createByCurve( edgeB, adsk.fusion.JointKeyPointTypes.MiddleKeyPoint )
                    
                    print( self.EdgeToString( edgeA ) )
                    print( self.EdgeToString( edgeB ) )
                    
                    jointInput = root.joints.createInput( joinA, joinB )
                    jointInput.offset = adsk.core.ValueInput.createByReal( offset )
                    jointInput.isFlipped = not self.AreEdgesInTheSameDirection( edgeA, edgeB )
                    jointInput.setAsRigidJointMotion()
                    root.joints.add( jointInput )
                    
                    return
        
    def notify( self, args ):
     try:
        eventArgs = adsk.core.CommandEventArgs.cast( args )
        inputs = eventArgs.command.commandInputs

        # Grab the design object (from which we can access the component hierarchy)
        app = adsk.core.Application.get()
        product = app.activeProduct
        design = adsk.fusion.Design.cast( product )
        
        name = inputs.itemById( value.Inputs.RootComponentName.id ).value
        root = self.CreateComponent( design.activeComponent, name )
        
        width = inputs.itemById( value.Inputs.BoxWidth.id ).value
        length = inputs.itemById( value.Inputs.BoxLength.id ).value
        height = inputs.itemById( value.Inputs.BoxHeight.id ).value
        materialThickness = inputs.itemById( value.Inputs.MaterialThickness.id ).value
        
        base = self.CreateBase( root, width, length, materialThickness )
        side = self.CreateSide( root, length, height, materialThickness )
        
        transform = adsk.core.Matrix3D.create()
        sideBOccurrence = root.occurrences.addExistingComponent( side, transform )

        self.Join( root, base, side, adsk.core.Point3D.create( 0, 0, 1 ) )
        self.Join( root, side, sideBOccurrence, adsk.core.Point3D.create( 1, 0, 0 ), -( width - materialThickness ) )
        
     except:
        app = adsk.core.Application.get()
        ui = app.userInterface
        import traceback
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))