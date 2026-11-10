/*
  Welding seam camera + laser carrier — FIT-CHECK PROTOTYPE ONLY
  Units: millimetres. Open this file in OpenSCAD.

  SAFETY / LIMITATIONS:
  - This is a visual/cold fit-check concept, not a production welding fixture.
  - NEVER install an FDM-printed plastic part on a live welding setup. Heat,
    arc UV/IR, molten spatter, fumes, vibration and collision risk require a
    reviewed metal mount, optical protection and supervisor approval.
  - The machine-side interface is not known from the photo. Four slots are a
    generic adaptation pattern; they are NOT verified to match the robot/torch.
  - Measure the laser's straight barrel before relying on the 12 mm bore.
  - Verify camera board size, hole pitch, and hole size on your exact board.

  Preview contains non-printable translucent proxies for the camera PCB/lens
  and laser module. Export BASE and YOKE separately for a cold fit-check.
*/

$fn = 64;

// ---------- EDITABLE PARAMETERS ----------
PART = "assembly";      // "assembly", "base", or "yoke"
show_proxies = true;    // visual dummies; should be false for STL export

plate_w = 130;
plate_h = 100;
plate_t = 6;
mount_slot_len = 18;
mount_slot_w = 6.6;
mount_x = 53;
mount_y = 37;

camera_board_w = 38;       // verify exact board
camera_hole_pitch = 34;    // verify exact hole centres
camera_hole_d = 2.8;       // verify exact PCB hole diameter
camera_x = 15;
camera_y = 0;
post_d = 6.5;
post_h = 8;
post_screw_pilot_d = 2.4;
lens_proxy_d = 16;         // visualization only
lens_proxy_h = 12;         // visualization only

laser_barrel_d = 12.0;     // MUST measure straight barrel with calipers
laser_bore_clearance = 0.5;
laser_clamp_outer_d = 20;
laser_clamp_len = 18;
laser_clamp_slit_w = 2.0;
laser_clamp_bolt_d = 3.2; // M3 clearance for cold mock-up
laser_angle_deg = 25;      // preview angle; physical angle adjusts 0–45 deg
laser_pivot_x = -33;
laser_pivot_y = 0;
laser_pivot_z = plate_t + 6;
laser_center_radius = 15;  // pivot-to-collar-centre distance
lock_radius = 28;          // radius of the locking bolt/arc slot
cheek_t = 3;
cheek_y = 13;
pivot_hole_d = 4.5;         // M4 clearance; hardware to be verified
lock_hole_d = 4.5;
arc_slot_d = 4.8;
rail_y = 9.1;
rail_t = 3.2;
rail_d = 7.0;

// ---------- HELPERS ----------
module rounded_slot_2d(length, width) {
    hull() {
        translate([-(length-width)/2, 0]) circle(d=width);
        translate([ +(length-width)/2, 0]) circle(d=width);
    }
}

module arc_slot_2d(radius, start_deg, end_deg, width, step=1.5) {
    for (a = [start_deg : step : end_deg-step]) {
        hull() {
            translate([radius*sin(a), radius*cos(a)]) circle(d=width);
            translate([radius*sin(a+step), radius*cos(a+step)]) circle(d=width);
        }
    }
    translate([radius*sin(end_deg), radius*cos(end_deg)]) circle(d=width);
}

// ---------- BASE: MOUNTING PLATE + CAMERA POSTS + FIXED HINGE CHEEKS ----------
module mounting_plate() {
    linear_extrude(height=plate_t)
        difference() {
            square([plate_w, plate_h], center=true);
            for (sx=[-1,1], sy=[-1,1])
                translate([sx*mount_x, sy*mount_y])
                    rounded_slot_2d(mount_slot_len, mount_slot_w);
        }
}

module camera_posts() {
    pitch = camera_hole_pitch/2;
    for (sx=[-1,1], sy=[-1,1]) {
        translate([camera_x + sx*pitch, camera_y + sy*pitch, plate_t])
            difference() {
                cylinder(d=post_d, h=post_h);
                translate([0,0,0.01]) cylinder(d=post_screw_pilot_d, h=post_h+0.02);
            }
    }
}

module fixed_cheek(ypos) {
    // Local 2D coordinates are (X, Z relative to pivot); arc slot runs 0–45°.
    translate([laser_pivot_x, ypos, laser_pivot_z])
        rotate([90,0,0])
            linear_extrude(height=cheek_t, center=true)
                difference() {
                    polygon(points=[[-27,-7],[27,-7],[27,32],[-27,32]]);
                    circle(d=pivot_hole_d);
                    arc_slot_2d(lock_radius, 0, 45, arc_slot_d, 1.5);
                }
}

module base_part() {
    union() {
        mounting_plate();
        camera_posts();
        fixed_cheek(-cheek_y);
        fixed_cheek(cheek_y);
    }
}

// ---------- MOVING LASER YOKE ----------
module laser_split_collar() {
    collar_bore = laser_barrel_d + laser_bore_clearance;
    outer_r = laser_clamp_outer_d/2;
    difference() {
        union() {
            cylinder(d=laser_clamp_outer_d, h=laser_clamp_len, center=true);
            // Ears either side of a split in the ring.
            for (sy=[-1,1])
                translate([-outer_r+1.2, sy*(laser_clamp_slit_w/2+2.1), 0])
                    cube([4.6, 4.2, laser_clamp_len], center=true);
        }
        cylinder(d=collar_bore, h=laser_clamp_len+1, center=true);
        translate([-outer_r-0.2, -laser_clamp_slit_w/2, -laser_clamp_len/2-0.5])
            cube([outer_r+0.4, laser_clamp_slit_w, laser_clamp_len+1]);
        // Transverse clamp screw through ring ears.
        translate([-outer_r+1.2, 0, 0])
            rotate([90,0,0]) cylinder(d=laser_clamp_bolt_d, h=16, center=true);
    }
}

module yoke_rail(ypos, theta) {
    // Round-ended rail from pivot to lock point. Rails flank the laser collar.
    hull() {
        translate([0, ypos, 0])
            rotate([90,0,0]) cylinder(d=rail_d, h=rail_t, center=true);
        translate([lock_radius*sin(theta), ypos, lock_radius*cos(theta)])
            rotate([90,0,0]) cylinder(d=rail_d, h=rail_t, center=true);
    }
}

module yoke_part() {
    theta = laser_angle_deg;
    center_x = laser_center_radius*sin(theta);
    center_z = laser_center_radius*cos(theta);
    difference() {
        union() {
            // Two side rails are slightly inside the ring's outer diameter;
            // they remain outside the laser's central optical bore.
            yoke_rail(-rail_y, theta);
            yoke_rail(rail_y, theta);
            translate([center_x, 0, center_z])
                rotate([0,theta,0]) laser_split_collar();
            // Pivot and lock bosses help the printed cold-fit prototype survive handling.
            for (yy=[-rail_y,rail_y]) {
                translate([0, yy, 0])
                    rotate([90,0,0]) cylinder(d=9, h=rail_t, center=true);
                translate([lock_radius*sin(theta), yy, lock_radius*cos(theta)])
                    rotate([90,0,0]) cylinder(d=9, h=rail_t, center=true);
            }
        }
        // Pivot hole through the yoke, along the Y axis.
        rotate([90,0,0]) cylinder(d=pivot_hole_d, h=40, center=true);
        // Locking bolt hole through each rail, aligned with the arc slot.
        translate([lock_radius*sin(theta), 0, lock_radius*cos(theta)])
            rotate([90,0,0]) cylinder(d=lock_hole_d, h=40, center=true);
    }
}

// ---------- VISUAL-ONLY HARDWARE PROXIES ----------
module camera_board_proxy() {
    color([0.12,0.30,0.16,0.9])
        translate([camera_x, camera_y, plate_t+post_h+0.8])
            cube([camera_board_w, camera_board_w, 1.6], center=true);
    color([0.05,0.05,0.05,0.95])
        translate([camera_x, camera_y, plate_t+post_h+1.6+lens_proxy_h/2])
            cylinder(d=lens_proxy_d, h=lens_proxy_h, center=true);
}

module laser_proxy() {
    theta = laser_angle_deg;
    center_x = laser_center_radius*sin(theta);
    center_z = laser_center_radius*cos(theta);
    color([0.72,0.72,0.75,0.95])
        translate([laser_pivot_x+center_x, laser_pivot_y, laser_pivot_z+center_z])
            rotate([0,theta,0])
                translate([0,0,10]) cylinder(d=laser_barrel_d, h=28, center=true);
}

module assembly_preview() {
    color([0.72,0.74,0.77]) base_part();
    // The yoke is positioned at the selected angle; in real assembly, M4 bolts
    // pass through pivot holes and arc slots to let it move between 0–45 degrees.
    color([0.45,0.49,0.54])
        translate([laser_pivot_x, laser_pivot_y, laser_pivot_z]) yoke_part();
    if (show_proxies) {
        camera_board_proxy();
        laser_proxy();
    }
}

if (PART == "base") {
    base_part();
} else if (PART == "yoke") {
    yoke_part();
} else {
    assembly_preview();
}
