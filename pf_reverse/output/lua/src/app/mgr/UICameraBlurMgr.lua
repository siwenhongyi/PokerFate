-- UI高斯模糊
local P = {}
UICameraBlurMgr = P

-- downSample 降采样系数
-- blurSize 模糊范围
-- blurIterations 迭代次数
function P:renderBlurImg(rawImage, downSample, blurSize, blurIterations)
	if not rawImage then
		return
	end

	local UiCameraBlur = CU.GameObject.Find("UIRoot/CameraRoot/UiCameraBlur")
	if not UiCameraBlur then
		printError("There is no UiCameraBlur.")
		return
	end

	local camera = UiCameraBlur:GetComponent("Camera")
	if not camera then
		printError("There is no camera component.")
		return
	end

	if not self.blurDestTex then
		self.blurDestTex = CS.Utils.GetTemporary(CU.Screen.width, CU.Screen.height, 0, CU.RenderTextureFormat.Default)
	end

	local sourceTex = CS.Utils.GetTemporary(CU.Screen.width, CU.Screen.height, 0, CU.RenderTextureFormat.Default)

	camera.targetTexture = sourceTex
	camera:Render()

	self:_renderBlur(sourceTex, self.blurDestTex, downSample, blurSize, blurIterations)

	rawImage:GetComponent("RawImage").texture = self.blurDestTex

	CU.RenderTexture.ReleaseTemporary(sourceTex)
end

function P:_renderBlur(sourceRt, destRt, downSample, blurSize, blurIterations)
	if not downSample then
		downSample = 3
	end

	if not blurSize then
		blurSize = 0.8
	end

	if not blurIterations then
		blurIterations = 2
	end

	local mat = ResManager:GetMaterial("material/UIGaussianBlur.mat")

	local rtW = sourceRt.width / downSample
	local rtH = sourceRt.height / downSample

	-- 降采样rt
	local rt0 = CS.Utils.GetTemporary(rtW, rtH, 0)
	rt0.filterMode = CU.FilterMode.Bilinear
	CS.Utils.GraphicsBlit(sourceRt, rt0)

	-- 迭代模糊
	for i = 1, blurIterations do
		mat:SetFloat("_BlurSize", blurSize * i + 1)

		local rt1 = CS.Utils.GetTemporary(rtW, rtH, 0)
		CS.Utils.GraphicsBlitWithMat(rt0, rt1, mat, 0)
		CU.RenderTexture.ReleaseTemporary(rt0)
		rt0 = rt1
		
		rt1 = CS.Utils.GetTemporary(rtW, rtH, 1)
		CS.Utils.GraphicsBlitWithMat(rt0, rt1, mat, 1)

		CU.RenderTexture.ReleaseTemporary(rt0)
		rt0 = rt1
	end

	CS.Utils.GraphicsBlit(rt0, destRt)
	CU.RenderTexture.ReleaseTemporary(rt0)
end

function P:clearBlurImg()
	if self.blurDestTex then
		CU.RenderTexture.ReleaseTemporary(self.blurDestTex)
		self.blurDestTex = nil
	end
end

function P:attachBlurRT()
	local UiCameraPostRT = CU.GameObject.Find("UIRoot/CameraRoot/UiCameraPostRT")
	if UiCameraPostRT then
		self._blurRT = CU.RenderTexture(SCREEN_WIDTH, SCREEN_HEIGHT, 0);
		UiCameraPostRT:GetComponent("Camera").targetTexture = self._blurRT
	end
end

function P:releaseBlurRT()
	if self._blurRT then
		self._blurRT:Release()
		self._blurRT = nil
	end
end

return P