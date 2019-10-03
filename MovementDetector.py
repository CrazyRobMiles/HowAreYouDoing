# Advanced Frame Differencing Example
#
# This example demonstrates using frame differencing with your OpenMV Cam. This
# example is advanced because it preforms a background update to deal with the
# backgound image changing overtime.

import sensor, image, pyb, os, time

TRIGGER_THRESHOLD = 5

BG_UPDATE_FRAMES = 20 # How many frames before blending.
BG_UPDATE_BLEND = 128 # How much to blend by... ([0-256]==[0.0-1.0]).

sensor.reset() # Initialize the camera sensor.
sensor.set_pixformat(sensor.RGB565) # or sensor.RGB565
sensor.set_framesize(sensor.QVGA) # or sensor.QQVGA (or others)
sensor.skip_frames(time = 2000) # Let new settings take affect.
sensor.set_auto_whitebal(False) # Turn off white balance.
clock = time.clock() # Tracks FPS.

# Take from the main frame buffer's RAM to allocate a second frame buffer.
# There's a lot more RAM in the frame buffer than in the MicroPython heap.
# However, after doing this you have a lot less RAM for some algorithms...
# So, be aware that it's a lot easier to get out of RAM issues now. However,
# frame differencing doesn't use a lot of the extra space in the frame buffer.
# But, things like AprilTags do and won't work if you do this...
extra_fb = sensor.alloc_extra_fb(sensor.width(), sensor.height(), sensor.RGB565)

print("About to save background image...")
sensor.skip_frames(time = 2000) # Give the user time to get ready.
extra_fb.replace(sensor.snapshot())
print("Saved background image - Now frame differencing!")

triggered = False

frame_count = 0

starting=True
last_x=0
last_y=0

TARGET_STARTING = 0
TARGET_MOVING_LEFT = 1
TARGET_MOVING_RIGHT = 2
TARGET_STOPPED = 3

target_state = TARGET_STARTING
tick_count = 0
tick_limit = 5

while(True):
    clock.tick() # Track elapsed milliseconds between snapshots().
    img = sensor.snapshot() # Take a picture and return the image.

    frame_count += 1
    if (frame_count > BG_UPDATE_FRAMES):
        frame_count = 0
        # Blend in new frame. We're doing 256-alpha here because we want to
        # blend the new frame into the backgound. Not the background into the
        # new frame which would be just alpha. Blend replaces each pixel by
        # ((NEW*(alpha))+(OLD*(256-alpha)))/256. So, a low alpha results in
        # low blending of the new image while a high alpha results in high
        # blending of the new image. We need to reverse that for this update.
        img.blend(extra_fb, alpha=(256-BG_UPDATE_BLEND))
        extra_fb.replace(img)

    # Replace the image with the "abs(NEW-OLD)" frame difference.
    img.difference(extra_fb)

    # Thresholds for determining the blobs that we are looking for in the
    # difference image

    lo=10
    hi=200
    move_tolerance = 80
    location_tolerance = 5

    tick_count = tick_count+1
    if tick_count < tick_limit:
        continue

    tick_count = 0


    # Get all the blobs in the difference image

    locations = ((48,'cupboard'),(187,'kettle'),(271,'sink'))

    def match_location(pos):
        for location in locations:
            loc_dist = abs(location[0] - pos)
            if loc_dist < location_tolerance:
                return location[1]
        return None

    blobs = img.find_blobs([(lo,hi),(lo,hi),(lo,hi)],area_threshold=2000,merge=True)

    target_state = TARGET_STARTING

    if len(blobs)>0:
        # We have got some blobs - find the largest one
        biggest_blob = max(blobs, key = lambda x: x.pixels())
        blob_x = biggest_blob.cx()
        blob_y = biggest_blob.cy()
        # find out how far the blob has moved
        x_change = last_x - blob_x
        #print("X:", blob_x," X change:",x_change)
        x_change = abs(x_change)
        if x_change > move_tolerance:
            img.draw_rectangle(biggest_blob.rect(),(255,0,0))
            if blob_x<last_x:
                # moving left
                if target_state != TARGET_MOVING_LEFT:
                    print("moving left")
                    target_state = TARGET_MOVING_LEFT
            else:
                # moving right
                if target_state != TARGET_MOVING_RIGHT:
                    print("Moving right")
                    target_state = TARGET_MOVING_RIGHT
        else:
            if target_state != TARGET_STOPPED:
                target_state = TARGET_STOPPED
                location = match_location(blob_x)
                if location != None:
                    img.draw_rectangle(biggest_blob.rect(),(0,0,255))
                    print("Stopped at:",location)
                else:
                    img.draw_rectangle(biggest_blob.rect(),(255,255,255))
                    #print("At:", blob_x)
        last_x = blob_x
        last_y = blob_y

    #hist = img.get_histogram()
    # This code below works by comparing the 99th percentile value (e.g. the
    # non-outlier max value against the 90th percentile value (e.g. a non-max
    # value. The difference between the two values will grow as the difference
    # image seems more pixels change.
    #diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()
    #triggered = diff > TRIGGER_THRESHOLD

#    print(clock.fps(), triggered) # Note: Your OpenMV Cam runs about half as fast while
    # connected to your computer. The FPS should increase once disconnected.
