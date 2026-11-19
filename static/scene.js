(() => {
  const canvas = document.getElementById('webgl-bg');
  if (!canvas || !window.THREE || matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.6));
  renderer.setSize(innerWidth, innerHeight, false);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x08090b, 0.055);
  const camera = new THREE.PerspectiveCamera(52, innerWidth / innerHeight, .1, 100);
  camera.position.set(0, 0, 11);

  const root = new THREE.Group();
  root.position.set(innerWidth > 850 ? 3.8 : 0, .7, -1.5);
  scene.add(root);

  const icoGeo = new THREE.IcosahedronGeometry(2.15, 2);
  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(icoGeo),
    new THREE.LineBasicMaterial({ color: 0xff762b, transparent: true, opacity: .28 })
  );
  root.add(wire);

  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.05, 1),
    new THREE.MeshBasicMaterial({ color: 0xff762b, wireframe: true, transparent: true, opacity: .15 })
  );
  root.add(core);

  const ringMat = new THREE.MeshBasicMaterial({ color: 0xffaa55, wireframe: true, transparent: true, opacity: .22 });
  const ring1 = new THREE.Mesh(new THREE.TorusGeometry(3.15, .018, 5, 160), ringMat);
  ring1.rotation.set(1.17, .2, .15);
  root.add(ring1);
  const ring2 = new THREE.Mesh(new THREE.TorusGeometry(2.68, .014, 5, 150), ringMat.clone());
  ring2.material.opacity = .13;
  ring2.rotation.set(.4, 1.05, .55);
  root.add(ring2);

  const particleCount = 460;
  const positions = new Float32Array(particleCount * 3);
  const colors = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i++) {
    const radius = 4 + Math.random() * 12;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i*3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i*3+1] = radius * Math.sin(phi) * Math.sin(theta) * .62;
    positions[i*3+2] = radius * Math.cos(phi);
    const warm = Math.random() > .78;
    colors[i*3] = warm ? 1 : .55;
    colors[i*3+1] = warm ? .45 : .5;
    colors[i*3+2] = warm ? .14 : .48;
  }
  const particlesGeo = new THREE.BufferGeometry();
  particlesGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particlesGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const particles = new THREE.Points(particlesGeo, new THREE.PointsMaterial({
    size: .038, transparent: true, opacity: .68, vertexColors: true, sizeAttenuation: true
  }));
  scene.add(particles);

  const pointer = { x: 0, y: 0 }, eased = { x: 0, y: 0 };
  addEventListener('pointermove', e => {
    pointer.x = (e.clientX / innerWidth - .5) * 2;
    pointer.y = (e.clientY / innerHeight - .5) * 2;
  }, { passive: true });
  addEventListener('resize', () => {
    renderer.setSize(innerWidth, innerHeight, false);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    root.position.x = innerWidth > 850 ? 3.8 : 0;
  });

  const clock = new THREE.Clock();
  let raf;
  function animate() {
    raf = requestAnimationFrame(animate);
    const elapsed = clock.getElapsedTime();
    eased.x += (pointer.x - eased.x) * .025;
    eased.y += (pointer.y - eased.y) * .025;
    wire.rotation.x = elapsed * .055 + eased.y * .11;
    wire.rotation.y = elapsed * .09 + eased.x * .15;
    core.rotation.x = -elapsed * .11;
    core.rotation.y = elapsed * .08;
    ring1.rotation.z = elapsed * .035;
    ring2.rotation.y = 1.05 - elapsed * .025;
    particles.rotation.y = elapsed * .006 + eased.x * .025;
    particles.rotation.x = eased.y * .018;
    camera.position.x = eased.x * .18;
    camera.position.y = -eased.y * .12;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
  }
  animate();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf); else animate();
  });
})();
