/*
  Adjustable welding seam sensor carrier - REVISION 2
  Units: mm. Open in OpenSCAD.

  STATUS: PARAMETRIC FIT-CHECK / DEVELOPMENT FIXTURE, NOT A CERTIFIED LIVE-WELD FIXTURE.

  Design intent from the supplied photos:
    - Camera board mounted in an open-frame holder so the rear 4-wire/USB lead
      connector has clearance and can be strain-relieved.
    - Camera pitch is adjustable in a slotted hinge; the support/yoke stays fixed.
    - Laser barrel is held vertically (optical end down; wires exit upwards).
    - Main backplate has strap slots for metal bands and optional M6 mounting slots.
    - A separate battery saddle is mounted on the rear/right side of the backplate;
      the saddle uses straps to retain the battery and keeps its terminals accessible.

  CRITICAL DIMENSIONS TO VERIFY BEFORE PRINTING:
    camera PCB outside dimensions, hole pitch/diameter, lens projection and connector;
    laser barrel diameter and length; actual robot/tool mount diameter; clearance and heat.
  Defaults are reasonable adjustable starting values, not dimensions proven from photos.

  DO NOT use FDM plastic parts on a live welding head without a safety/thermal review.
  Heat, UV/IR, spatter, vibration, robot collision and cable snagging can cause failure.
  Use these parts for bench/cold fit checks. For live welding, use a reviewed metal
  mount or place the polymer assembly in a suitable cool/shielded location.
*/

$fn = 64;

// ===================== USER PARAMETERS =====================
PART = "assembly";  // assembly, base, camera_yoke, camera_carrier, laser_bracket, laser_collar, battery_saddle
show_proxies = true;
show_machine_proxy = false;

// Machine adapter/backplate: use two stainless metal bands through the long slots,
// or use the optional edge mounting slots if the actual machine has matching fasteners.
plate_w = 150;
plate_h = 100;
plate_t = 6;
band_slot_len = 82;
band_slot_w = 10.5;       // for a band no wider than this; verify band width
band_slot_z = 42;
edge_slot_x = 66;
edge_slot_len = 20;
edge_slot_w = 6.6;        // nominal M6 clearance slot

// Camera board holder: defaults based on visual estimate only; measure the exact PCB.
camera_board_w = 38;
camera_hole_pitch = 31;   // provisional; edit after measuring hole-centre spacing
camera_hole_slot_len = 7.0;
camera_hole_d = 2.8;      // nominal M2.5 clearance; verify board holes/screws
camera_frame_w = 50;
camera_frame_h = 50;
camera_frame_t = 4.0;
camera_frame_aperture = 36;
camera_pivot_boss_x = 28;
camera_pivot_boss_d = 10;
camera_bolt_d = 4.5;      // nominal M4 pivot clearance
camera_tilt_lock_radius = 22;
camera_tilt_min_deg = 20;
camera_tilt_max_deg = 85;
camera_tilt_deg = 70;      // positive points the lens toward -Y and downward (-Z)

// Camera yoke pan platform and fixed shelf.
camera_mount_x = -8;
pan_pivot_y = 12;
camera_shelf_z = -18;
camera_shelf_t = 5;
camera_shelf_w = 80;
camera_shelf_d = 64;
yoke_cheek_x = 34;
yoke_cheek_t = 4;
yoke_pivot_y = 28;
yoke_pivot_z = 32;
yoke_pan_plate_t = 5;
yoke_pan_plate_w = 80;
yoke_pan_plate_d = 54;
yoke_pan_plate_center_y = 22;

// Laser: measure the smooth cylindrical barrel with calipers before printing.
laser_x = -8;
laser_z = -10;
laser_barrel_d = 12.0;    // PROVISIONAL: do not use until measured
laser_bore_clearance = 0.5;
laser_collar_outer_d = 22;
laser_collar_h = 16;
laser_split_gap = 2.0;
laser_clamp_bolt_d = 3.4; // nominal M3 clearance
laser_mount_bolt_d = 4.5;
laser_mount_plate_w = 30;
laser_mount_plate_h = 54;
laser_mount_plate_t = 4;
laser_collar_y = 21;

// Rear battery holder. Sized to fit a common rectangular 9 V battery provisionally;
// verify the actual battery/pack and terminal orientation before printing.
battery_mount_x = 38;
battery_mount_z = 5;
battery_mount_hole_pitch_z = 38;
battery_saddle_w = 48;
battery_saddle_h = 62;
battery_saddle_t = 3.2;
battery_rail_h = 5;
battery_strap_slot_w = 8.0;
battery_strap_slot_len = 34;
battery_proxy_w = 26.5;
battery_proxy_t = 17.5;
battery_proxy_h = 48.5;

// ===================== HELPER GEOMETRY =====================
module rounded_slot_2d(length, width) {
  hull() {
    translate([-(length-width)/2, 0]) circle(d=width);
    translate([(length-width)/2, 0]) circle(d=width);
  }
}

// Rounded slot cut through Y, drawn in the X-Z plane.
module slot_through_y(x, z, length, width, angle=0, depth=plate_t+2) {
  translate([x, 0, z]) rotate([90,0,0])
    linear_extrude(height=depth, center=true)
      rotate([0,0,angle]) rounded_slot_2d(length,width);
}

module hole_through_y(x,z,d,depth=plate_t+2) {
  translate([x,0,z]) rotate([90,0,0]) cylinder(d=d,h=depth,center=true);
}

// Arc slot in a horizontal XY plate. Angle is measured from +Y, x=r*sin(a), y=r*cos(a).
module arc_slot_xy(radius, start_deg, end_deg, width, zcenter, depth, step=5) {
  for (a=[start_deg:step:end_deg-step]) {
    hull() {
      translate([radius*sin(a),radius*cos(a),zcenter]) cylinder(d=width,h=depth,center=true);
      translate([radius*sin(a+step),radius*cos(a+step),zcenter]) cylinder(d=width,h=depth,center=true);
    }
  }
  translate([radius*sin(end_deg),radius*cos(end_deg),zcenter]) cylinder(d=width,h=depth,center=true);
}

// Arc slot in a Y-Z profile: theta=0 is +Z, negative theta moves toward +Y.
module arc_slot_yz_2d(radius,start_deg,end_deg,width,step=4) {
  for (a=[start_deg:step:end_deg-step]) {
    hull() {
      translate([-radius*sin(a),radius*cos(a)]) circle(d=width);
      translate([-radius*sin(a+step),radius*cos(a+step)]) circle(d=width);
    }
  }
  translate([-radius*sin(end_deg),radius*cos(end_deg)]) circle(d=width);
}

module xz_profile_extrude_y(points, depth) {
  rotate([90,0,0]) linear_extrude(height=depth,center=true) polygon(points=points);
}

// ===================== FIXED MACHINE BACKPLATE =====================
module fixed_camera_shelf() {
  // Fixed shelf; the camera yoke is bolted to it. Camera angle changes only at the tilt hinge.
  difference() {
    translate([camera_mount_x, camera_shelf_d/2 - 2, camera_shelf_z])
      cube([camera_shelf_w,camera_shelf_d,camera_shelf_t],center=true);
    for (sx=[-1,1], yy=[10,34])
      translate([camera_mount_x + sx*30, pan_pivot_y + yy, camera_shelf_z])
        cylinder(d=4.5,h=camera_shelf_t+2,center=true);
    // U-shaped centre clearance around the vertical laser mount and barrel.
    translate([laser_x,19,camera_shelf_z]) cube([34,40,camera_shelf_t+2],center=true);
  }
}

module camera_shelf_gusset(xcenter) {
  // Triangular rib runs from the backplate out under the shelf; kept outside the moving yoke cheeks.
  translate([xcenter,0,0]) rotate([90,0,90]) linear_extrude(height=4,center=true)
    polygon(points=[[0,camera_shelf_z-2],[0,camera_shelf_z-28],[50,camera_shelf_z-2]]);
}

module base_part() {
  union() {
    difference() {
      cube([plate_w,plate_t,plate_h],center=true);
      // Two long slots for stainless band clamps around a suitable cool, rigid cylindrical section.
      for (z=[-band_slot_z,band_slot_z])
        slot_through_y(0,z,band_slot_len,band_slot_w,0,plate_t+2);
      // Optional vertical M6-ish mounting slots near the edges; only use if these align with real hardware.
      for (x=[-edge_slot_x,edge_slot_x])
        slot_through_y(x,0,edge_slot_len,edge_slot_w,90,plate_t+2);
      // Laser bracket four-hole pattern. These holes accept M4 bolts into the laser bracket.
      for (sx=[-1,1], sz=[-1,1])
        hole_through_y(laser_x + sx*9, laser_z + sz*14, laser_mount_bolt_d, plate_t+2);
      // Rear-mounted battery saddle: two M4 fixing holes; the holder is outside the camera shelf.
      for (sz=[-1,1])
        hole_through_y(battery_mount_x, battery_mount_z + sz*battery_mount_hole_pitch_z/2, 4.5, plate_t+2);
    }
    fixed_camera_shelf();
    // Shelf gussets: one each side, not in the camera's central optical path.
    camera_shelf_gusset(camera_mount_x-38);
    camera_shelf_gusset(camera_mount_x+38);
  }
}

// ===================== CAMERA PAN + TILT YOKE =====================
module yoke_cheek_2d() {
  difference() {
    polygon(points=[[-4,0],[22,0],[47,14],[49,34],[46,48],[36,57],[22,60],[8,51],[-4,30]]);
    translate([yoke_pivot_y,yoke_pivot_z]) circle(d=camera_bolt_d);
    translate([yoke_pivot_y,yoke_pivot_z])
      arc_slot_yz_2d(camera_tilt_lock_radius,camera_tilt_min_deg,camera_tilt_max_deg,5.0);
  }
}

module camera_yoke_part() {
  union() {
    difference() {
      translate([0,yoke_pan_plate_center_y,0])
        cube([yoke_pan_plate_w,yoke_pan_plate_d,yoke_pan_plate_t],center=true);
      // Four M4 clearance holes bolt the yoke rigidly to the shelf.
      for (sx=[-1,1], yy=[10,34])
        translate([sx*30,yy,0]) cylinder(d=4.5,h=yoke_pan_plate_t+2,center=true);
      // Matching U-notch clears the fixed vertical laser and its collar.
      translate([laser_x-camera_mount_x,7,0]) cube([34,40,yoke_pan_plate_t+2],center=true);
    }
    // Two side cheeks; the two curved slots provide the camera pitch adjustment.
    for (sx=[-1,1])
      translate([sx*yoke_cheek_x,0,0]) rotate([90,0,90])
        linear_extrude(height=yoke_cheek_t,center=true) yoke_cheek_2d();
  }
}

// ===================== CAMERA CARRIER / OPEN FRAME =====================
module camera_hole_slot(sx,sz) {
  // Radial diagonal slots allow small adjustment to the exact PCB hole pitch.
  angle = (sx*sz > 0) ? 45 : -45;
  slot_through_y(sx*camera_hole_pitch/2,sz*camera_hole_pitch/2,
                 camera_hole_slot_len,camera_hole_d,angle,camera_frame_t+3);
}

module x_axis_hollow_boss(xc,zc,outer_d=10,inner_d=4.5,len=8) {
  translate([xc,0,zc]) rotate([0,90,0]) difference() {
    cylinder(d=outer_d,h=len,center=true);
    cylinder(d=inner_d,h=len+1,center=true);
  }
}

module camera_carrier_part() {
  union() {
    difference() {
      cube([camera_frame_w,camera_frame_t,camera_frame_h],center=true);
      cube([camera_frame_aperture,camera_frame_t+2,camera_frame_aperture],center=true);
      for (sx=[-1,1],sz=[-1,1]) camera_hole_slot(sx,sz);
    }
    // Side trunnions align with the tilt pivot axis; top locking lugs track through the cheek arc slots.
    for (sx=[-1,1]) {
      x_axis_hollow_boss(sx*camera_pivot_boss_x,0,camera_pivot_boss_d,4.5,8);
      x_axis_hollow_boss(sx*camera_pivot_boss_x,camera_tilt_lock_radius,9.5,4.5,8);
    }
    // Small rear cable-guide bridge at one side of the top edge; the central connector area remains open.
    translate([0,4, camera_frame_h/2+2])
      difference() {
        cube([20,8,4],center=true);
        cube([12,3.5,6],center=true);
      }
  }
}

// ===================== LASER BRACKET AND COLLAR =====================
module laser_split_collar() {
  outer_r = laser_collar_outer_d/2;
  inner_d = laser_barrel_d + laser_bore_clearance;
  difference() {
    union() {
      cylinder(d=laser_collar_outer_d,h=laser_collar_h,center=true);
      // Compression ears on both sides of the split.
      for (sy=[-1,1])
        translate([-outer_r+1.3,sy*(laser_split_gap/2+1.5),0])
          cube([4.5,3.2,laser_collar_h],center=true);
    }
    cylinder(d=inner_d,h=laser_collar_h+2,center=true);
    // Radial slit at negative X; leaves a compressible ring.
    translate([-outer_r-0.5,-laser_split_gap/2,-laser_collar_h/2-1])
      cube([outer_r+1,laser_split_gap,laser_collar_h+2]);
    // M3 pinch bolt runs along Y through the ears.
    translate([-outer_r+1.3,0,0]) rotate([90,0,0])
      cylinder(d=laser_clamp_bolt_d,h=14,center=true);
  }
}

module laser_bracket_part() {
  // Local origin is the laser optical axis at the centre of the collar.
  union() {
    difference() {
      translate([0,4,0]) cube([laser_mount_plate_w,laser_mount_plate_t,laser_mount_plate_h],center=true);
      for (sx=[-1,1],sz=[-1,1])
        translate([sx*9,4,sz*14]) rotate([90,0,0]) cylinder(d=laser_mount_bolt_d,h=laser_mount_plate_t+2,center=true);
    }
    // Compact bridge/standoff from mounting flange to collar. Its back remains clear for wires.
    translate([0,8,0]) cube([12,12,10],center=true);
    // Fixed vertical collar: Z axis; output/aperture points down (-Z), leads are above (+Z).
    translate([0,laser_collar_y,0]) laser_split_collar();
    // Raised cable strain-relief: clip sits above the laser's rear/wire end.
    translate([8,9,24]) cube([8,12,4],center=true);
    translate([8,15,24])
      difference() {
        cube([12,6,4],center=true);
        cube([7,8,2.8],center=true);
      }
  }
}

// ===================== REAR-MOUNTED BATTERY SADDLE =====================
// This is an X-Z plate with its thickness along Y, matching the main backplate.
// It sits behind the backplate; the pack lies against its rear face and is retained
// with two narrow straps/Velcro through the slots. Terminals/wires face upward.
module battery_saddle_part() {
  union() {
    difference() {
      cube([battery_saddle_w,battery_saddle_t,battery_saddle_h],center=true);
      // Two 8 mm slots for hook-and-loop or narrow battery straps.
      for (zz=[-12,12])
        slot_through_y(0,zz,battery_strap_slot_len,battery_strap_slot_w,0,battery_saddle_t+2);
      // Two M4 screws fix this holder to the main backplate.
      for (sz=[-1,1])
        hole_through_y(0,sz*battery_mount_hole_pitch_z/2,4.5,battery_saddle_t+2);
    }
    // Shallow side rails and a lower stop project away from the backplate, not toward the camera.
    for (xx=[-(battery_proxy_w/2+2),battery_proxy_w/2+2])
      translate([xx,-battery_saddle_t/2-battery_rail_h/2,0])
        cube([3,battery_rail_h,battery_saddle_h-8],center=true);
    translate([0,-battery_saddle_t/2-battery_rail_h/2,-battery_proxy_h/2+1.5])
      cube([battery_proxy_w+8,battery_rail_h,3],center=true);
  }
}

module machine_proxy() {
  // Visual-only cylinder depicting one possible cylindrical mount location. Not exported to STLs.
  color([0.14,0.15,0.17,0.25]) translate([0,-55,0]) rotate([90,0,0]) cylinder(d=58,h=100,center=true);
}

module assembly_preview() {
  if (show_machine_proxy) machine_proxy();
  color([0.69,0.72,0.75,1]) base_part();
  // Laser mount attaches to the front of the plate; the laser remains vertical.
  color([0.45,0.48,0.52,1]) translate([laser_x,0,laser_z]) laser_bracket_part();
  // Camera yoke is fixed to the backplate; loosen the side locks to adjust pitch.
  translate([camera_mount_x,pan_pivot_y,camera_shelf_z+camera_shelf_t/2+yoke_pan_plate_t/2]) {
    color([0.42,0.45,0.49,1]) camera_yoke_part();
    translate([0,yoke_pivot_y,yoke_pivot_z]) rotate([camera_tilt_deg,0,0]) {
      color([0.22,0.24,0.27,1]) camera_carrier_part();
      if (show_proxies) camera_proxy();
    }
  }
  if (show_proxies) translate([laser_x,0,laser_z]) laser_proxy();
  // Rear mounted battery saddle and illustrative battery proxy. The printed saddle is a separate part.
  translate([battery_mount_x,-plate_t/2-battery_saddle_t/2,battery_mount_z]) {
    color([0.47,0.49,0.52,1]) battery_saddle_part();
    if (show_proxies)
      translate([0,-battery_saddle_t/2-battery_proxy_t/2,0]) {
        color([0.16,0.17,0.19,1]) cube([battery_proxy_w,battery_proxy_t,battery_proxy_h],center=true);
        for (xx=[-3.8,3.8])
          color([0.72,0.73,0.75,1])
            translate([xx,0,battery_proxy_h/2+1])
              cylinder(d=4.5,h=2,center=true);
      }
  }
}

// Part selection: separate printable solid(s), no visual-only proxies.
if (PART == "base") {
  base_part();
} else if (PART == "camera_yoke") {
  camera_yoke_part();
} else if (PART == "camera_carrier") {
  camera_carrier_part();
} else if (PART == "laser_bracket") {
  laser_bracket_part();
} else if (PART == "laser_collar") {
  laser_split_collar();
} else if (PART == "battery_saddle") {
  battery_saddle_part();
} else {
  assembly_preview();
}
