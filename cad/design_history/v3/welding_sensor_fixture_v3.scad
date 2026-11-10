/*
  WELDING SEAM SENSOR FIXTURE - REVISION 3
  Camera (tilting, lockable) + laser (fixed) side by side + torch-neck clamp.
  Units: mm.  +Z = direction the sensors look (toward the torch tip / weld).

  Hardware this is cut for (from the photos and the measured values):
    - Arducam UC-852 board: 38 x 38 mm, 4 corner holes 5 mm from each edge
      (28 mm pitch), hole dia 3.5-4 mm  -> M3 screws into pilot bosses.
    - Laser module: dia 11 mm (V-cradle accepts 10-13), length 35 mm,
      emitting end = knurled brass ring, wires out of the rear centre.
    - Robot MIG torch: round swan neck / torch body. The clamp is a V-saddle
      strapped with two stainless worm-drive hose clamps, so it fits any
      round section from ~16 mm to ~65 mm diameter without re-printing.

  PARTS (set PART below, press F6, File > Export > STL):
    "base"        base plate + camera cheeks + laser V-cradle + ribs  (print flat)
    "camera_yoke" tilting camera carrier with trunnion ears           (print flat, bosses up)
    "laser_bar"   laser clamp bar                                     (print flat face down)
    "arm_clamp"   torch-neck V-saddle block                           (print on its SIDE)
    "assembly"    everything together with visual-only proxies (not printable)

  Fasteners:
    camera board -> yoke bosses : 4x M3 x 8  (self-tapping into 2.7 mm pilot)
    yoke pivot (2x)             : M4 x 12 + M4 nut (nut captive in the ear) + M4 washer
    yoke tilt lock (2x)         : M4 x 12 + M4 nut (nut captive in the ear) + M4 washer
    laser clamp bar (2x)        : M3 x 25 + M3 nut (nut captive in the cradle back)
    arm clamp -> base (4x)      : M4 x 16 + M4 nut (nut captive in the block)
    arm clamp -> torch (2x)     : stainless worm-drive hose clamps, band <= 13 mm wide
*/

$fn = 72;

// ============================ PART SELECTION ============================
PART = "assembly";      // assembly | base | camera_yoke | laser_bar | arm_clamp
show_proxies = true;    // visual-only sensors / torch neck in the assembly view
camera_tilt_deg = 20;   // preview only. Physical range: -15 .. +45 (toward the laser is positive)

// ============================ MEASURED HARDWARE ============================
cam_board_w     = 38;    // square PCB
cam_hole_edge   = 5;     // hole centre distance from PCB edge
cam_hole_pitch  = cam_board_w - 2*cam_hole_edge;   // = 28
cam_board_t     = 1.6;
cam_lens_d      = 16;    // proxy only
cam_lens_h      = 14;    // proxy only

laser_d         = 11;    // body diameter (V accepts 10..13)
laser_len       = 35;
laser_ring_d    = 12.5;  // front knurled ring (proxy only)

neck_proxy_d    = 20;    // torch neck diameter shown in the preview only

// ============================ BASE PLATE ============================
plate_t   = 6;
plate_x0  = -68;         // clamp end (V-notch end)
plate_x1  = 86;          // camera end
plate_w   = 70;          // Y
plate_corner_r = 5;

rib_h  = 10;             // edge stiffening ribs on top of the plate
rib_t  = 4;

// ============================ TORCH CLAMP BLOCK ============================
blk_x0 = -68;  blk_x1 = -22;        // block footprint on the plate (X)
blk_w  = 46;                        // Y
blk_h  = 56;                        // along the neck (Z), sits on the plate top
v_apex_x = -53;                     // 90 deg V, apex X (depth 15, opening 30 wide at the face)
band_slot_x0 = -50.5;  band_slot_t = 2.6;    // hose-clamp band slots, through the block in Y
band_slot_h  = 14;                            // band width allowed
band_slot_z  = [18, 38];                      // slot bottoms above the plate top
clamp_bolt_xy = [[-58,-15],[-58,15],[-28,-15],[-28,15]];
m4_clear = 4.5;
m4_nut_af = 7.3;   m4_nut_t = 3.6;           // captive-nut pockets
nut_z_center = 6;                             // nut centre height above the plate top (inside the block)

// ============================ LASER CRADLE ============================
laser_x = 0;  laser_y = 0;                    // optical axis position on the plate
lv_depth = 10;                                // V depth in the cradle block
lv_apex_x = laser_x + (laser_d/2)/sin(45);    // laser centre lands exactly on laser_x for laser_d
lblk_x1 = lv_apex_x + 6.2;                    // block back face (+X)
lblk_x0 = lv_apex_x - lv_depth;               // block front face (-X, the V opens this way)
lblk_w  = 30;                                 // Y
lblk_h  = 24;                                 // Z above the plate
lbar_v_depth = 3;
lbar_t  = 5;
lbar_h  = 14;
lbar_z0 = 4;                                  // bar bottom above the plate top
lbar_screw_y = 9;                             // the two M3 screws straddle the laser
lbar_screw_z = lbar_z0 + lbar_h/2;
m3_clear = 3.4;
m3_nut_af = 5.9;  m3_nut_pocket_depth = 5;
laser_wire_hole_d = 8;                        // through the plate under the laser rear end

// ============================ CAMERA YOKE ============================
cam_x   = 55;                                 // camera centre on the plate
pivot_z = 39.5;                               // pivot axis height above plate bottom (z=0)
car_len = 50;  car_w = 48;  car_t = 4;        // carrier slab (X, Y, thickness)
car_top_z = pivot_z - 5.5;                    // slab top; pivot is at board level
boss_d = 7;  boss_h = 8;  boss_pilot_d = 2.7; // M3 self-tap bosses
car_window = 22;
ear_t = 6;                                    // trunnion ear thickness (Y)
ear_y0 = 21;                                  // ear inner face |y|
ear_r  = 7;
lock_r = 22;                                  // tilt-lock bolt radius from the pivot
tilt_min = -15;  tilt_max = 45;               // arc-slot range
cheek_gap = 0.6;
cheek_t  = 4;
cheek_y0 = ear_y0 + ear_t + cheek_gap;        // = 27.8
arc_slot_w = 4.8;
pivot_hole_d = 4.5;

// ============================ HELPERS ============================
module rslot2d(len, w) { hull() { translate([-(len-w)/2,0]) circle(d=w); translate([(len-w)/2,0]) circle(d=w); } }
module hex2d(af) { circle(d = af/cos(30), $fn=6); }
module zip_slot(x, y, along_y=true) {   // 3 x 6 mm zip-tie slot through the plate
  translate([x,y,-1]) linear_extrude(plate_t+2) rotate(along_y?90:0) rslot2d(6,3);
}
// XZ profile extruded along Y, centred on y=0 with thickness t
module xz_extrude(t) { rotate([90,0,0]) linear_extrude(height=t, center=true) children(); }

// Rotation used for the camera tilt: positive = optical axis leans toward -X (toward the laser)
module tilt(a) { rotate([0,-a,0]) children(); }

// 90-degree V cut, axis along Z, opening toward -X, apex at (ax, ay); 'depth' toward -X
module v_cut_z(ax, ay, depth, z0, z1) {
  translate([ax, ay, z0]) linear_extrude(z1-z0)
    polygon([[0,0],[-depth-1, depth+1],[-depth-1,-depth-1]]);
}

// ============================ BASE PLATE ============================
module plate_outline2d() {
  difference() {
    hull() {
      translate([plate_x0, -plate_w/2]) square([1, plate_w]);
      translate([plate_x1-plate_corner_r,  plate_w/2-plate_corner_r]) circle(r=plate_corner_r);
      translate([plate_x1-plate_corner_r, -plate_w/2+plate_corner_r]) circle(r=plate_corner_r);
    }
    // V-notch for the torch neck (same V as the clamp block)
    translate([v_apex_x,0]) polygon([[0,0],[-16,16],[-16,-16]]);
  }
}

module cheek_profile2d() {   // absolute XZ coords
  difference() {
    polygon([[22,plate_t-0.01],[72,plate_t-0.01],[72,36],[64,50],[36,54],[24,48],[22,36]]);
    translate([cam_x, pivot_z]) circle(d=pivot_hole_d);
    // arc slot: angle 0 = toward -X, positive = downward (camera tilting toward the laser)
    translate([cam_x, pivot_z])
      for (a=[tilt_min:2:tilt_max-2]) hull() {
        translate([-lock_r*cos(a),   -lock_r*sin(a)])   circle(d=arc_slot_w);
        translate([-lock_r*cos(a+2), -lock_r*sin(a+2)]) circle(d=arc_slot_w);
      }
  }
}

module cheek_ticks(sy) {    // engraved angle ticks on the outer cheek face
  for (a=[tilt_min:15:tilt_max])
    translate([cam_x, sy*(cheek_y0+cheek_t), pivot_z])
      rotate([0,0,0])
        translate([-29.5*cos(a), 0, -29.5*sin(a)])
          rotate([0,-a,0]) cube([3.0, 1.4, (a==0)?1.6:1.0], center=true);
}

module laser_cradle() {
  difference() {
    translate([lblk_x0, -lblk_w/2, plate_t-0.01]) cube([lblk_x1-lblk_x0, lblk_w, lblk_h+0.01]);
    v_cut_z(lv_apex_x, laser_y, lv_depth, plate_t-1, plate_t+lblk_h+1);
    // two M3 clamp screws straddle the laser, nuts captive at the back face
    for (sy=[-1,1]) {
      translate([lblk_x0-1, laser_y+sy*lbar_screw_y, plate_t+lbar_screw_z])
        rotate([0,90,0]) cylinder(d=m3_clear, h=lblk_x1-lblk_x0+2);
      translate([lblk_x1-m3_nut_pocket_depth, laser_y+sy*lbar_screw_y, plate_t+lbar_screw_z])
        rotate([0,90,0]) linear_extrude(m3_nut_pocket_depth+1) hex2d(m3_nut_af);
    }
  }
}

module base_part() {
  difference() {
    union() {
      linear_extrude(plate_t) plate_outline2d();
      // edge ribs
      for (sy=[-1,1]) translate([blk_x1, sy*(plate_w/2-rib_t/2)-rib_t/2, plate_t-0.01]) cube([plate_x1-plate_corner_r-blk_x1, rib_t, rib_h]);
      // camera cheeks
      for (sy=[-1,1]) translate([0, sy*(cheek_y0+cheek_t/2), 0]) xz_extrude(cheek_t) cheek_profile2d();
      laser_cradle();
    }
    // clamp-block bolts
    for (p=clamp_bolt_xy) translate([p[0],p[1],-1]) cylinder(d=m4_clear, h=plate_t+2);
    // laser wires straight down through the plate
    translate([laser_x, laser_y, -1]) cylinder(d=laser_wire_hole_d, h=plate_t+2);
    // zip-tie slots: laser wires (under the clamp bar side) and camera cable
    for (sy=[-1,1]) zip_slot(laser_x-12, sy*7);
    for (sy=[-1,1]) zip_slot(cam_x-18, sy*8);
    // camera cable pass-through under the carrier
    translate([cam_x,0,-1]) linear_extrude(plate_t+2) rslot2d(20,8);
    // angle ticks
    for (sy=[-1,1]) cheek_ticks(sy);
  }
}

// ============================ CAMERA YOKE ============================
module ear_profile2d() {   // relative to the pivot, XZ
  hull() {
    circle(r=ear_r);
    translate([-lock_r,0]) circle(r=ear_r);
    translate([-car_len/2, car_top_z-pivot_z-car_t]) square([car_len, car_t]);
  }
}

module camera_yoke_part() {   // modelled in place (tilt = 0)
  difference() {
    union() {
      translate([cam_x-car_len/2, -car_w/2, car_top_z-car_t]) cube([car_len, car_w, car_t]);
      for (sx=[-1,1], sy=[-1,1])
        translate([cam_x+sx*cam_hole_pitch/2, sy*cam_hole_pitch/2, car_top_z-0.01]) cylinder(d=boss_d, h=boss_h+0.01);
      for (sy=[-1,1]) translate([cam_x, sy*(ear_y0+ear_t/2), pivot_z]) xz_extrude(ear_t) ear_profile2d();
    }
    // M3 pilots
    for (sx=[-1,1], sy=[-1,1])
      translate([cam_x+sx*cam_hole_pitch/2, sy*cam_hole_pitch/2, car_top_z+boss_h-7]) cylinder(d=boss_pilot_d, h=8);
    // central window for the rear components / connector, plus a cable notch toward +X
    translate([cam_x, 0, car_top_z-car_t-1]) linear_extrude(car_t+2) square(car_window, center=true);
    translate([cam_x+car_window/2-1, -5, car_top_z-car_t-1]) cube([car_len/2+2, 10, car_t+2]);
    // zip-tie slots beside the notch
    for (sy=[-1,1]) translate([cam_x+car_len/2-4, sy*10, car_top_z-car_t-1]) linear_extrude(car_t+2) rotate(90) rslot2d(6,3);
    // pivot and lock holes through the ears + captive hex pockets on the inner faces
    for (sy=[-1,1]) for (lx=[0,-lock_r]) {
      translate([cam_x+lx, 0, pivot_z]) rotate([90,0,0]) cylinder(d=pivot_hole_d, h=80, center=true);
      translate([cam_x+lx, sy*(ear_y0-1), pivot_z]) rotate([-90*sy,0,0]) linear_extrude(m4_nut_t+1) rotate(30) hex2d(m4_nut_af);
    }
  }
}

// ============================ LASER CLAMP BAR ============================
module laser_bar_part() {   // modelled in place
  bar_apex_x = laser_x - (laser_d/2)/sin(45);
  bar_x1 = bar_apex_x + lbar_v_depth;      // flat inner face
  bar_x0 = bar_x1 - lbar_t;
  difference() {
    translate([bar_x0, -lblk_w/2, plate_t+lbar_z0]) cube([lbar_t, lblk_w, lbar_h]);
    // shallow V on the inner face (opens toward +X)
    translate([bar_apex_x, laser_y, plate_t+lbar_z0-1]) linear_extrude(lbar_h+2)
      polygon([[0,0],[lbar_v_depth+1, lbar_v_depth+1],[lbar_v_depth+1,-lbar_v_depth-1]]);
    for (sy=[-1,1])
      translate([bar_x0-1, laser_y+sy*lbar_screw_y, plate_t+lbar_screw_z]) rotate([0,90,0]) cylinder(d=m3_clear, h=lbar_t+2);
  }
}

// ============================ TORCH CLAMP BLOCK ============================
module arm_clamp_part() {   // modelled in place on the plate
  z0 = plate_t;
  difference() {
    translate([blk_x0, -blk_w/2, z0]) cube([blk_x1-blk_x0, blk_w, blk_h]);
    v_cut_z(v_apex_x, 0, 16, z0-1, z0+blk_h+1);
    // hose-clamp band slots through the block (Y direction)
    for (zb=band_slot_z) translate([band_slot_x0, -blk_w/2-1, z0+zb]) cube([band_slot_t, blk_w+2, band_slot_h]);
    // 4x M4 bolt holes from the plate side, blind, with side-entry captive nut traps
    for (p=clamp_bolt_xy) {
      translate([p[0],p[1],z0-1]) cylinder(d=m4_clear, h=nut_z_center+10);
      if (p[0] < v_apex_x) {
        // nose bolts: nut slides in from the +/-Y face
        sy = sign(p[1]);
        translate([p[0]-m4_nut_af/2, (sy>0)?p[1]-m4_nut_af/cos(30)/2:-blk_w/2-1, z0+nut_z_center-m4_nut_t/2])
          cube([m4_nut_af, (sy>0)?(blk_w/2-p[1]+m4_nut_af/cos(30)/2+1):(blk_w/2+p[1]+m4_nut_af/cos(30)/2+1), m4_nut_t]);
      } else {
        // rear bolts: nut slides in from the +X face
        translate([p[0]-m4_nut_af/cos(30)/2, p[1]-m4_nut_af/2, z0+nut_z_center-m4_nut_t/2])
          cube([blk_x1-p[0]+m4_nut_af/cos(30)/2+1, m4_nut_af, m4_nut_t]);
      }
    }
    // chamfer the V edges a little so a large torch body seats on them cleanly
  }
}

// ============================ VISUAL PROXIES ============================
module camera_proxy() {   // in place, tilt = 0
  color([0.10,0.12,0.14]) translate([cam_x-cam_board_w/2, -cam_board_w/2, car_top_z+boss_h]) cube([cam_board_w, cam_board_w, cam_board_t]);
  color([0.05,0.05,0.05]) translate([cam_x, 0, car_top_z+boss_h+cam_board_t]) cylinder(d=cam_lens_d, h=cam_lens_h);
  color([0.85,0.75,0.3]) for (sx=[-1,1], sy=[-1,1]) translate([cam_x+sx*cam_hole_pitch/2, sy*cam_hole_pitch/2, car_top_z+boss_h+cam_board_t]) cylinder(d=5.5, h=2);
  color([0.95,0.95,0.95,0.6]) translate([cam_x, 0, car_top_z+boss_h+cam_board_t+cam_lens_h]) cylinder(d1=3, d2=40, h=90); // field of view hint
}
module laser_proxy() {
  color([0.75,0.75,0.78]) translate([laser_x, laser_y, plate_t]) cylinder(d=laser_d, h=laser_len-5);
  color([0.80,0.65,0.30]) translate([laser_x, laser_y, plate_t+laser_len-5]) cylinder(d=laser_ring_d, h=5);
  color([1,0,0,0.6]) translate([laser_x, laser_y, plate_t+laser_len]) cylinder(d=1.2, h=100);
}
module neck_proxy() {
  r = neck_proxy_d/2;
  color([0.6,0.6,0.62,0.35]) translate([v_apex_x - r/sin(45), 0, -40]) cylinder(d=neck_proxy_d, h=160);
}

module assembly() {
  color([0.70,0.72,0.75]) base_part();
  color([0.45,0.48,0.52]) arm_clamp_part();
  color([0.40,0.42,0.46]) laser_bar_part();
  color([0.25,0.27,0.30]) yoke_tilted();
  if (show_proxies) proxies();
}

// ============================ OUTPUT ============================
// Print orientations: every exported part lies on z=0 in the orientation it should be printed.
module bar_on_bed()   { rotate([0,-90,0]) translate([-(laser_x-(laser_d/2)/sin(45)+lbar_v_depth-lbar_t), 0, -(plate_t+lbar_z0)]) laser_bar_part(); }
module clamp_on_bed() { translate([0,0,blk_w/2]) rotate([-90,0,0]) translate([0,0,-plate_t]) arm_clamp_part(); }
module yoke_on_bed()  { translate([-cam_x, 0, -(car_top_z-car_t)]) camera_yoke_part(); }
module yoke_tilted()  { translate([cam_x,0,pivot_z]) tilt(camera_tilt_deg) translate([-cam_x,0,-pivot_z]) camera_yoke_part(); }
module proxies()      { translate([cam_x,0,pivot_z]) tilt(camera_tilt_deg) translate([-cam_x,0,-pivot_z]) camera_proxy(); laser_proxy(); neck_proxy(); }

if (PART == "base")                    base_part();
else if (PART == "camera_yoke")        yoke_on_bed();
else if (PART == "laser_bar")          bar_on_bed();
else if (PART == "arm_clamp")          clamp_on_bed();
// in-place variants (verification / assembly viewing only)
else if (PART == "yoke_inplace")       yoke_tilted();
else if (PART == "bar_inplace")        laser_bar_part();
else if (PART == "clamp_inplace")      arm_clamp_part();
else if (PART == "proxies")            proxies();
else                                   assembly();
