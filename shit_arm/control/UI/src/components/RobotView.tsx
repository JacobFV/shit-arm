import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import type { RobotModel } from '../ws/types'

interface JointPivot {
  pivot: THREE.Group
  axis: THREE.Vector3
  baseQuaternion: THREE.Quaternion
}

interface RobotViewProps {
  model: RobotModel | undefined
  joints: number[]
  gripper: number
}

const JOINT_ORDER = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']

export function RobotView({ model, joints, gripper }: RobotViewProps) {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const rootRef = useRef<THREE.Group | null>(null)
  const pivotsRef = useRef<Map<string, JointPivot>>(new Map())
  const frameRef = useRef<number | null>(null)
  const orbitRef = useRef({ yaw: -0.62, pitch: 0.52, distance: 0.68 })
  const dragRef = useRef({ active: false, x: 0, y: 0 })
  const modelKey = model ? `${model.name}:${model.asset_base_url}` : ''

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0d0f13)
    const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 10)
    camera.up.set(0, 0, 1)
    updateCameraOrbit(camera, orbitRef.current)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    mount.appendChild(renderer.domElement)

    scene.add(new THREE.HemisphereLight(0xd7dee8, 0x1a2028, 2.6))
    const key = new THREE.DirectionalLight(0xffffff, 3.2)
    key.position.set(0.35, -0.65, 0.75)
    scene.add(key)

    const grid = new THREE.GridHelper(1.25, 12, 0x26313d, 0x202833)
    grid.rotation.x = Math.PI / 2
    scene.add(grid)

    const root = new THREE.Group()
    scene.add(root)

    sceneRef.current = scene
    cameraRef.current = camera
    rendererRef.current = renderer
    rootRef.current = root

    const render = () => {
      const rect = mount.getBoundingClientRect()
      renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false)
      camera.aspect = rect.width / Math.max(1, rect.height)
      camera.updateProjectionMatrix()
      updateCameraOrbit(camera, orbitRef.current)
      renderer.render(scene, camera)
      frameRef.current = requestAnimationFrame(render)
    }
    render()

    const onPointerDown = (event: PointerEvent) => {
      dragRef.current = { active: true, x: event.clientX, y: event.clientY }
      renderer.domElement.setPointerCapture(event.pointerId)
    }
    const onPointerMove = (event: PointerEvent) => {
      if (!dragRef.current.active) return
      const dx = event.clientX - dragRef.current.x
      const dy = event.clientY - dragRef.current.y
      dragRef.current = { active: true, x: event.clientX, y: event.clientY }
      orbitRef.current.yaw += dx * 0.008
      orbitRef.current.pitch = Math.max(-0.95, Math.min(1.15, orbitRef.current.pitch + dy * 0.008))
    }
    const onPointerUp = (event: PointerEvent) => {
      dragRef.current.active = false
      if (renderer.domElement.hasPointerCapture(event.pointerId)) {
        renderer.domElement.releasePointerCapture(event.pointerId)
      }
    }
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      orbitRef.current.distance = Math.max(0.24, Math.min(1.45, orbitRef.current.distance + event.deltaY * 0.0008))
    }

    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointermove', onPointerMove)
    renderer.domElement.addEventListener('pointerup', onPointerUp)
    renderer.domElement.addEventListener('pointercancel', onPointerUp)
    renderer.domElement.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointermove', onPointerMove)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('pointercancel', onPointerUp)
      renderer.domElement.removeEventListener('wheel', onWheel)
      renderer.dispose()
      renderer.domElement.remove()
      scene.clear()
    }
  }, [])

  useEffect(() => {
    const root = rootRef.current
    if (!root || !model) return

    root.clear()
    pivotsRef.current.clear()

    const loader = new STLLoader()
    const linkGroups = new Map<string, THREE.Group>()
    const childLinks = new Set<string>()

    for (const link of model.links || []) {
      const group = new THREE.Group()
      group.name = link.name
      linkGroups.set(link.name, group)

      for (const visual of link.visuals || []) {
        const holder = new THREE.Group()
        applyOrigin(holder, visual.origin)
        group.add(holder)

        const geometry = visual.geometry
        if (!geometry) continue

        const material = materialForColor(visual.color)
        if (geometry.type === 'mesh' && geometry.filename) {
          loader.load(`${model.asset_base_url}/${geometry.filename}`, (stlGeometry) => {
            stlGeometry.computeVertexNormals()
            const mesh = new THREE.Mesh(stlGeometry, material)
            if (geometry.scale) mesh.scale.fromArray(geometry.scale)
            holder.add(mesh)
          })
        } else {
          const primitive = primitiveGeometry(geometry)
          if (primitive) holder.add(new THREE.Mesh(primitive, material))
        }
      }
    }

    for (const joint of model.joints || []) {
      if (!joint.parent || !joint.child) continue
      const parent = linkGroups.get(joint.parent)
      const child = linkGroups.get(joint.child)
      if (!parent || !child) continue

      const pivot = new THREE.Group()
      applyOrigin(pivot, joint.origin)
      parent.add(pivot)
      pivot.add(child)
      childLinks.add(joint.child)
      pivotsRef.current.set(joint.name, {
        pivot,
        axis: vectorFromArray(joint.axis),
        baseQuaternion: pivot.quaternion.clone(),
      })
    }

    for (const [name, group] of linkGroups) {
      if (!childLinks.has(name)) root.add(group)
    }
  }, [modelKey])

  useEffect(() => {
    for (const [index, jointName] of JOINT_ORDER.entries()) {
      const joint = pivotsRef.current.get(jointName)
      if (!joint) continue
      const value = jointName === 'gripper' ? gripper : Number(joints[index] ?? 0)
      const rotation = new THREE.Quaternion().setFromAxisAngle(joint.axis.clone().normalize(), value)
      joint.pivot.quaternion.copy(joint.baseQuaternion).multiply(rotation)
    }
  }, [joints, gripper])

  return (
    <div className="robot-view">
      <div ref={mountRef} className="robot-view__canvas" />
      <div className="robot-view__status">{model ? `${model.name} URDF` : 'waiting for robot model'}</div>
    </div>
  )
}

function updateCameraOrbit(camera: THREE.PerspectiveCamera, orbit: { yaw: number; pitch: number; distance: number }) {
  const target = new THREE.Vector3(-0.04, -0.015, 0.08)
  const cp = Math.cos(orbit.pitch)
  camera.position.set(
    target.x + Math.sin(orbit.yaw) * cp * orbit.distance,
    target.y + Math.cos(orbit.yaw) * cp * orbit.distance,
    target.z + Math.sin(orbit.pitch) * orbit.distance,
  )
  camera.lookAt(target)
}

function applyOrigin(object: THREE.Object3D, origin: { xyz: number[]; rpy: number[] }) {
  object.position.fromArray(origin.xyz || [0, 0, 0])
  const rpy = origin.rpy || [0, 0, 0]
  object.rotation.set(rpy[0], rpy[1], rpy[2], 'XYZ')
}

function vectorFromArray(values: number[]) {
  return new THREE.Vector3(values[0] ?? 0, values[1] ?? 0, values[2] ?? 1)
}

function materialForColor(color: number[] | null) {
  const rgba = color || [0.7, 0.74, 0.78, 1]
  return new THREE.MeshStandardMaterial({
    color: new THREE.Color(rgba[0], rgba[1], rgba[2]),
    roughness: 0.58,
    metalness: 0.05,
    transparent: rgba[3] < 1,
    opacity: rgba[3],
  })
}

function primitiveGeometry(geometry: NonNullable<RobotModel['links'][number]['visuals'][number]['geometry']>) {
  if (geometry.type === 'box' && geometry.size) return new THREE.BoxGeometry(...geometry.size)
  if (geometry.type === 'sphere' && geometry.radius) return new THREE.SphereGeometry(geometry.radius, 24, 16)
  if (geometry.type === 'cylinder' && geometry.radius && geometry.length) {
    return new THREE.CylinderGeometry(geometry.radius, geometry.radius, geometry.length, 32).rotateX(Math.PI / 2)
  }
  return null
}
