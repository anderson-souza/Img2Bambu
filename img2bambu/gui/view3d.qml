import QtQuick
import QtQuick3D
import QtQuick3D.Helpers

Item {
    id: root
    property var parts: []

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment { clearColor: "#d0d0d0"; backgroundMode: SceneEnvironment.Color }

        Node {
            id: orbit
            objectName: "orbit"
            PerspectiveCamera { id: cam; objectName: "camera"; z: 300 }
        }
        DirectionalLight { eulerRotation.x: -30; eulerRotation.y: -30 }
        DirectionalLight { eulerRotation.x: 60; brightness: 0.5 }

        // why: meshes are Z-up mm like the export; Qt Quick 3D is Y-up
        Node {
            eulerRotation.x: -90
            Model {
                objectName: "bed"
                source: "#Rectangle"
                visible: false
                materials: PrincipledMaterial { baseColor: "#bdbdbd"; roughness: 0.9 }
            }
            Node {
                objectName: "model"
                Repeater3D {
                    objectName: "parts"
                    model: root.parts
                    Model {
                        geometry: modelData.geometry
                        materials: PrincipledMaterial { baseColor: modelData.color; roughness: 0.6 }
                    }
                }
            }
        }
    }

    OrbitCameraController { anchors.fill: parent; origin: orbit; camera: cam }
}
