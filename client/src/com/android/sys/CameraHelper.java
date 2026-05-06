package com.android.sys;

import android.content.Context;
import android.graphics.ImageFormat;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CaptureRequest;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.os.HandlerThread;

import java.io.FileOutputStream;
import java.util.Arrays;

public class CameraHelper {

    public interface PhotoCallback {
        void onPhotoSaved(String path);
        void onError(String error);
    }

    public static void takePhoto(
            Context context,
            boolean frontCamera,
            String outputPath,
            PhotoCallback callback) {

        HandlerThread thread = new HandlerThread("CamThread");
        thread.start();
        Handler handler = new Handler(thread.getLooper());

        try {
            CameraManager manager = (CameraManager)
                    context.getSystemService(Context.CAMERA_SERVICE);

            String cameraId = null;
            int wanted = frontCamera
                    ? CameraCharacteristics.LENS_FACING_FRONT
                    : CameraCharacteristics.LENS_FACING_BACK;

            for (String id : manager.getCameraIdList()) {
                CameraCharacteristics chars = manager.getCameraCharacteristics(id);
                Integer facing = chars.get(CameraCharacteristics.LENS_FACING);
                if (facing != null && facing == wanted) {
                    cameraId = id;
                    break;
                }
            }
            if (cameraId == null) {
                cameraId = manager.getCameraIdList()[0];
            }

            final ImageReader reader =
                    ImageReader.newInstance(1280, 720, ImageFormat.JPEG, 2);

            reader.setOnImageAvailableListener(r -> {
                try {
                    Image image = r.acquireLatestImage();
                    if (image != null) {
                        Image.Plane[] planes = image.getPlanes();
                        java.nio.ByteBuffer buf = planes[0].getBuffer();
                        byte[] data = new byte[buf.remaining()];
                        buf.get(data);
                        image.close();
                        FileOutputStream fos = new FileOutputStream(outputPath);
                        fos.write(data);
                        fos.close();
                        callback.onPhotoSaved(outputPath);
                    }
                } catch (Exception e) {
                    callback.onError("Save error: " + e.getMessage());
                } finally {
                    reader.close();
                    thread.quit();
                }
            }, handler);

            manager.openCamera(cameraId, new CameraDevice.StateCallback() {
                @Override
                public void onOpened(CameraDevice camera) {
                    try {
                        CaptureRequest.Builder builder =
                                camera.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
                        builder.addTarget(reader.getSurface());

                        camera.createCaptureSession(
                                Arrays.asList(reader.getSurface()),
                                new CameraCaptureSession.StateCallback() {
                                    @Override
                                    public void onConfigured(CameraCaptureSession session) {
                                        try {
                                            session.capture(builder.build(), null, handler);
                                        } catch (Exception e) {
                                            camera.close();
                                            callback.onError("Capture error: " + e.getMessage());
                                        }
                                    }
                                    @Override
                                    public void onConfigureFailed(CameraCaptureSession session) {
                                        camera.close();
                                        callback.onError("Configure failed");
                                    }
                                },
                                handler);
                    } catch (Exception e) {
                        camera.close();
                        callback.onError("Session error: " + e.getMessage());
                    }
                }

                @Override
                public void onDisconnected(CameraDevice camera) {
                    camera.close();
                }

                @Override
                public void onError(CameraDevice camera, int error) {
                    camera.close();
                    callback.onError("Camera error code: " + error);
                }
            }, handler);

        } catch (Exception e) {
            callback.onError("Open error: " + e.getMessage());
            thread.quit();
        }
    }
}
