/*
  PRINTED HARDWARE KIT for welding_sensor_fixture_v3  (no metal screws, nuts or hose clamps)
  Units: mm. Every part fits the holes and pockets ALREADY in the 4 printed v3 parts.

  Parts (set PART, F6, export STL). Print in PETG if possible (PLA works, is more brittle).
    "camera_pin"        4 (+2 spare)  push pins: camera board -> camera yoke bosses
    "yoke_pin"          4 (+2 spare)  snap pins: camera tilt pivot (2) + lock (2)
    "angle_plate_R"     1 per angle    locks the camera tilt angle, RIGHT cheek (+Y side)
    "angle_plate_L"     1 per angle    same, LEFT cheek (-Y side)          (set ANGLE)
    "block_pin"         4 (+1 spare)  joins torch clamp block to base plate
    "block_fork"        4 (+1 spare)  locking fork for each block pin (slides into the nut slot)
    "laser_clip"        1 per size     replaces laser bar + 2 screws (SIZE 1 = 10.6, 2 = 11.0, 3 = 11.4 mm laser);
                                       spring beam gives the clamping force, no screws
    "strap_short"       2              ratchet strap, torch neck 16-35 mm (replaces hose clamps)
    "strap_long"        2              ratchet strap, torch neck 35-65 mm (needs 220 x 220 bed, print diagonally)
    "inplace_*"         verification only (parts placed in v3 coordinates)

  The v3 laser_bar.stl is NOT used with this kit (the laser clip replaces it).
*/

$fn = 48;
PART = "yoke_pin";
ANGLE = 20;        // camera tilt for the angle plates, degrees (-15 .. 45)
SIZE = 2;          // laser clip size 1/2/3

// ------------------------------------------------------------ v3 geometry (copied from welding_sensor_fixture_v3.scad)
plate_t = 6;
cam_x = 55;  pivot_z = 39.5;  lock_r = 22;
ear_y0 = 21; ear_t = 6; cheek_gap = 0.6; cheek_t = 4;
cheek_y0 = ear_y0 + ear_t + cheek_gap;       // 27.6  cheek inner face
cheek_out = cheek_y0 + cheek_t;              // 31.6  cheek outer face
pocket_shoulder = ear_y0 - 1 + 3.6 + 1;      // 24.6  bottom of the hex pocket in the ear (from inside)
hole_d = 4.5;  slot_w = 4.8;  tilt_min = -15;  tilt_max = 45;
car_top_z = 34;  boss_top = 42;  cam_pitch = 28;  pilot_d = 2.7;  pilot_depth = 7;  board_t = 1.6;
blk_x1 = -22;  blk_w = 46;  trap_z0 = 10.2;  trap_z1 = 13.8;  trap_af = 7.3;  bolt_hole_top = 21;
block_bolts = [[-58,-15],[-58,15],[-28,-15],[-28,15]];
laser_d_design = 11;  cradle_apex = 7.7782;  cradle_back = 13.9782;  cradle_w = 30;  cradle_front = -2.2218;
bar_z0 = 10;  bar_h = 14;
band_slot_t = 2.6;  band_slot_h = 14;

// ------------------------------------------------------------ helpers
// Seven-segment digits (no fonts needed). Height 5, width 3, stroke 0.7.
SEG = [[1,1,1,1,1,1,0],[0,1,1,0,0,0,0],[1,1,0,1,1,0,1],[1,1,1,1,0,0,1],[0,1,1,0,0,1,1],
       [1,0,1,1,0,1,1],[1,0,1,1,1,1,1],[1,1,1,0,0,0,0],[1,1,1,1,1,1,1],[1,1,1,1,0,1,1]];
module digit2d(d, h=5, w=3, s=0.7) {
  segs = [[0,h-s,w,s],[w-s,h/2,s,h/2],[w-s,0,s,h/2],[0,0,w,s],[0,0,s,h/2],[0,h/2,s,h/2],[0,h/2-s/2,w,s]];
  for (i=[0:6]) if (SEG[d][i]==1) translate([segs[i][0],segs[i][1]]) square([segs[i][2],segs[i][3]]);
}
module number2d(n, h=5) {  // non-negative integer up to 99; minus sign drawn as a bar
  a = abs(n);
  if (n < 0) translate([-2.2,h/2-0.35]) square([1.6,0.7]);
  if (a >= 10) { digit2d(floor(a/10), h, h*0.6); translate([h*0.6+0.8,0]) digit2d(a%10, h, h*0.6); }
  else digit2d(a, h, h*0.6);
}

// A pin lying along +X, printed flat: round body with two flats (top/bottom) for strength and bed contact.
module dpin_body(len, d, flat) { intersection() { rotate([0,90,0]) cylinder(d=d, h=len); translate([0,-d,-flat/2]) cube([len, 2*d, flat]); } }

// ============================================================ 1. camera push pin
// head 6.5 x 1.2 | neck 3.3 through the board (1.6) | tapered stem 2.55 -> 2.95 pressed 6 mm into the 2.7 pilot
module camera_pin() {
  cylinder(d=6.5, h=1.2);
  translate([0,0,1.2]) cylinder(d=3.3, h=board_t);
  translate([0,0,1.2+board_t]) cylinder(d1=2.95, d2=2.55, h=6);
}

// ============================================================ 2. yoke snap pin
// grip = angle plate (2.5) + cheek (4) + gap (0.6) + ear hole part (2.4) + 0.1 = 9.6
plate_th = 2.5;
yoke_grip = plate_th + cheek_t + cheek_gap + (ear_y0 + ear_t - pocket_shoulder) + 0.1;
module yoke_pin() {
  d = 4.3; flat = 3.8; split_w = 1.2; barb_w = 5.3; barb_len = 3.0; head_l = 2.0;
  difference() {
    union() {
      translate([-head_l, -4.5, -flat/2]) cube([head_l, 9, flat]);                    // T head 9 x 3.8
      dpin_body(yoke_grip, d, flat);
      // barbs: shoulder at x = grip, taper to the tip
      translate([0,0,-flat/2]) linear_extrude(flat)
        polygon([[yoke_grip-0.01,-barb_w/2],[yoke_grip+0.4,-barb_w/2],[yoke_grip+barb_len,-1.9],
                 [yoke_grip+barb_len,1.9],[yoke_grip+0.4,barb_w/2],[yoke_grip-0.01,barb_w/2]]);
    }
    // split: the two prongs squeeze together through the 4.5 mm holes
    translate([2.5, -split_w/2, -flat]) cube([yoke_grip + barb_len, split_w, 2*flat]);
  }
}

// ============================================================ 3. angle lock plate
// In the cheek plane: u = X - cam_x, v = Z - pivot_z. Lock hole at angle a: (-r cos a, -r sin a).
function lockpt(a, r=lock_r) = [-r*cos(a), -r*sin(a)];
key_w = 4.2;  key_h = cheek_t - 0.6;  key_gap_deg = 12.5;
module key_arc2d(a0, a1) {
  if (a1 - a0 > 0.5)
    for (a=[a0:1:a1-1]) hull() { translate(lockpt(a)) circle(d=key_w); translate(lockpt(min(a+1,a1))) circle(d=key_w); }
}
module plate_outline2d(ang) {
  lo0 = tilt_min; lo1 = ang - key_gap_deg; hi0 = ang + key_gap_deg; hi1 = tilt_max;
  a_min = (lo1 - lo0 >= 2) ? lo0 : ang;
  a_max = (hi1 - hi0 >= 2) ? hi1 : ang;
  hull() {
    circle(r=7.5);
    for (a=[a_min:2:a_max]) translate(lockpt(a)) circle(r=4.6);
    translate(lockpt(a_max)) circle(r=4.6);
    translate(lockpt(ang)) circle(r=5.5);
  }
}
module angle_plate_local(ang, flip_text=false) {  // z=0 is the face that touches the cheek; key goes to -z
  lo0 = tilt_min; lo1 = ang - key_gap_deg; hi0 = ang + key_gap_deg; hi1 = tilt_max;
  difference() {
    union() {
      linear_extrude(plate_th) plate_outline2d(ang);
      translate([0,0,-key_h]) linear_extrude(key_h + 0.01) {
        if (lo1 - lo0 >= 2) key_arc2d(lo0, lo1);
        if (hi1 - hi0 >= 2) key_arc2d(hi0, hi1);
      }
    }
    translate([0,0,-10]) cylinder(d=4.6, h=20);
    translate(concat(lockpt(ang), -10)) cylinder(d=4.6, h=20);
    // engraved angle number on the outside face
    translate([-9.5, 3.5, plate_th - 0.6]) linear_extrude(1)
      if (flip_text) translate([0, 8]) mirror([0,1,0]) number2d(ang, 4); else number2d(ang, 4);
  }
}
// placed on a cheek: side +1 = right (+Y), -1 = left (-Y)
module angle_plate_inplace(ang, side) {
  // local (u, v, w) -> world (x - cam_x, side*w, z - pivot_z): w is the outward normal, key goes inward
  translate([cam_x, side*cheek_out, pivot_z])
    rotate([-side*90, 0, 0]) {
      if (side > 0) mirror([0,1,0]) angle_plate_local(ang, true);
      else angle_plate_local(ang, false);
    }
}

// ============================================================ 4. block pin + fork
// pin from the BACK of the base plate (z<0 is outside) up into the clamp block.
block_neck_d = 2.6;
module block_pin_flat() {  // along +X, x=0 = plate bottom face, head at x<0
  d = 4.3; flat = 3.8;
  translate([-2, -4.5, -flat/2]) cube([2, 9, flat]);                           // head under the plate
  difference() {
    dpin_body(trap_z1 + 2.0, d, flat);                                          // to 2 mm above the slot
    translate([trap_z0 - 0.05, 0, 0]) rotate([0,90,0])
      difference() { cylinder(d=d+1, h=trap_z1 - trap_z0 + 0.1); cylinder(d=block_neck_d, h=trap_z1 - trap_z0 + 0.1); }
  }
}
module block_pin() { rotate([0,-90,0]) block_pin_flat(); }   // standing: +X -> +Z
// fork: slides into the nut slot from the block face, straddles the pin neck. Detent mouth 2.4 < neck 2.6.
module block_fork(face_dist) {   // face_dist = pin centre to block face (6 rear, 8 side)
  w = 7.0; t = 3.3; back = 4.0; tab = 3.0;
  len = back + face_dist + tab;
  difference() {
    translate([-back, -w/2, 0]) cube([len, w, t]);
    // seat for the neck at x=0, opening toward -x (the end that goes in first)
    translate([0,0,-1]) cylinder(d=block_neck_d + 0.25, h=t+2);
    translate([-back-1, -1.2, -1]) cube([back+1, 2.4, t+2]);
    // grip tab ridges
    for (i=[0:2]) translate([face_dist + 0.6 + i*0.9, -w/2-1, t-0.5]) cube([0.45, w+2, 1]);
  }
}

// ============================================================ 5. laser clip
// U clip. A V pad presses the laser into the cradle V. The pad hangs on a thin SPRING BEAM (3 mm)
// that spans between two arms; the arms run along the cradle sides and hook behind its back face.
// The pad is built 'clip_preload' deeper than the laser surface, so the beam bends ~0.6 mm when
// fitted: about 40 N (PETG) clamping force. Sizes for laser diameter 10.6 / 11.0 / 11.4 mm.
clip_preload = 0.6;
function clip_laser_d(s) = s == 1 ? 10.6 : (s == 3 ? 11.4 : 11.0);
module laser_clip(size=2) {
  d = clip_laser_d(size);
  apex = cradle_apex - 1.4142*d + clip_preload;  // relaxed V apex (contact apex + preload)
  vdep = 4.5;  pad_back = 1.5;  pad_w = 12;  beam_t = 3.0;
  arm_y0 = cradle_w/2 + 0.25;  arm_t = 2.6;  lip = 2.0;  lip_t = 2.4;
  hook = cradle_back;                            // lip face touches the cradle back face
  beam_x0 = apex - pad_back - beam_t;
  translate([0,0,bar_z0]) linear_extrude(bar_h) {
    difference() {
      translate([apex - pad_back, -pad_w/2]) square([pad_back + vdep, pad_w]);          // V pad
      translate([apex, 0]) polygon([[0,0],[vdep+1, vdep+1],[vdep+1,-(vdep+1)]]);
    }
    translate([beam_x0, -(arm_y0 + arm_t)]) square([beam_t, 2*(arm_y0 + arm_t)]);       // spring beam
    for (s=[-1,1]) {
      translate([beam_x0, s > 0 ? arm_y0 : -(arm_y0 + arm_t)]) square([hook - beam_x0 + lip_t, arm_t]);   // arm
      translate([hook, s*arm_y0]) polygon(s > 0 ? [[0,0],[lip_t,0],[lip_t,0.01],[0.2,-lip],[0,-lip]]
                                               : [[0,0],[lip_t,0],[lip_t,-0.01],[0.2,lip],[0,lip]]);   // hook + lead-in
    }
  }
  // size mark: 1, 2 or 3 small bumps on top of the +Y arm
  for (i=[0:size-1]) translate([beam_x0 + 6 + i*3, arm_y0 + arm_t/2, bar_z0 + bar_h - 0.01]) cylinder(d=1.6, h=0.6);
}

// ============================================================ 6. ratchet strap (replaces hose clamps)
st_w = 12;  st_base = 1.4;  st_tooth = 0.8;  st_pitch = 1.6;
head_l = 13;  head_w = 18;  head_h = 7;  ch_w = 4.85;  ch_l = st_w + 0.8;  wall = 2.6;
module strap(body_len) {
  // head (x<0), channel along Z; pawl tongue anchored at the bottom, pointing up (+Z = insertion direction)
  cx0 = -head_l + wall;  cx1 = cx0 + ch_w;
  difference() {
    translate([-head_l, -head_w/2, 0]) cube([head_l, head_w, head_h]);
    translate([cx0, -ch_l/2, -1]) cube([ch_w, ch_l, head_h + 2]);
    // arrow (insert direction marker) engraved on top: points toward the channel
    translate([cx1 + 0.8, 0, head_h - 0.5]) linear_extrude(1) polygon([[0,-2],[2.2,0],[0,2]]);
  }
  // pawl tongue: thickness 0.9, length 6, slanted 22 deg from vertical; tip overlaps the teeth by 0.55 mm
  translate([0, -(ch_l-0.8)/2, 0]) rotate([90,0,0]) mirror([0,0,1]) linear_extrude(ch_l - 0.8) {
    hull() { translate([cx0 + 0.4, 0.8]) circle(d=0.9); translate([cx0 + 0.5 + 6*sin(22), 0.8 + 6*cos(22)]) circle(d=0.9); }
    translate([cx0 - 0.01, 0]) square([1.0, 1.6]);   // root: fused to the channel wall and the bed
  }
  // strap body with sawtooth on top: vertical face on the head side, ramp descending toward the tail
  tail_taper = 15;
  teeth_from = 8;
  difference() {
    union() {
      hull() { translate([-0.01, -st_w/2, 0]) cube([body_len - tail_taper, st_w, st_base]);
               translate([body_len - 0.5, -4, 0]) cube([0.5, 8, st_base]); }
      intersection() {
        for (x=[teeth_from:st_pitch:body_len - st_pitch])
          translate([x, st_w/2, st_base - 0.01]) rotate([90,0,0]) linear_extrude(st_w)
            polygon([[0,0],[0,st_tooth],[st_pitch,0]]);
        hull() { translate([-0.01, -st_w/2, 0]) cube([body_len - tail_taper, st_w, 5]);
                 translate([body_len - 0.5, -4, 0]) cube([0.5, 8, 5]); }
      }
    }
  }
}

// ============================================================ in-place placements (verification only)
module yoke_pin_inplace(side, u, v) {   // pin axis along Y, head outside
  translate([cam_x + u, side*(cheek_out + plate_th), pivot_z + v]) rotate([0,0,-side*90]) yoke_pin();
}
module camera_pins_inplace() {
  for (sx=[-1,1], sy=[-1,1]) translate([cam_x + sx*cam_pitch/2, sy*cam_pitch/2, boss_top + board_t + 1.2]) mirror([0,0,1]) camera_pin();
}
module block_pins_inplace() { for (p=block_bolts) translate([p[0], p[1], 0]) block_pin(); }
module block_forks_inplace() {
  for (p=block_bolts) {
    rear = p[0] > -53;
    translate([p[0], p[1], trap_z0 + 0.15])
      rotate([0,0, rear ? 0 : (p[1] > 0 ? 90 : -90)]) block_fork(rear ? (blk_x1 - p[0]) : (blk_w/2 - abs(p[1])));
  }
}

// ============================================================ output (print orientation unless inplace)
if (PART == "camera_pin") camera_pin();
else if (PART == "yoke_pin") translate([2, 0, 1.9]) yoke_pin();
else if (PART == "angle_plate_R") translate([0,0,plate_th]) rotate([180,0,0]) mirror([0,1,0]) angle_plate_local(ANGLE, true);
else if (PART == "angle_plate_L") translate([0,0,plate_th]) rotate([180,0,0]) angle_plate_local(ANGLE, false);
else if (PART == "block_pin") translate([2,0,1.9]) block_pin_flat();
else if (PART == "block_fork_rear") block_fork(6);
else if (PART == "block_fork_side") block_fork(8);
else if (PART == "laser_clip") translate([0,0,-bar_z0]) laser_clip(SIZE);
else if (PART == "strap_short") strap(185);
else if (PART == "strap_long") strap(260);
else if (PART == "inplace_yoke_pins") {
  for (s=[-1,1]) { yoke_pin_inplace(s, 0, 0); yoke_pin_inplace(s, lockpt(ANGLE)[0], lockpt(ANGLE)[1]); }
}
else if (PART == "inplace_angle_plates") { angle_plate_inplace(ANGLE, 1); angle_plate_inplace(ANGLE, -1); }
else if (PART == "inplace_camera_pins") camera_pins_inplace();
else if (PART == "inplace_block_pins") block_pins_inplace();
else if (PART == "inplace_block_forks") block_forks_inplace();
else if (PART == "inplace_laser_clip") laser_clip(SIZE);
