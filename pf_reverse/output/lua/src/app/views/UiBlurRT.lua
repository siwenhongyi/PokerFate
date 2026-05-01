local P = class("UiBlurRT", UiBase)

function P:onAwake()
    self.UiCameraPostRT = self:find("UiCameraPostRT", self.node)
    self.UiCanvaPostRT = self:find("UiCanvaPostRT", self.node)

    self._blurRT = CU.RenderTexture(SCREEN_WIDTH, SCREEN_HEIGHT, 0);
    self.UiCameraPostRT:GetComponent("Camera").targetTexture = self._blurRT

    local cmp = self.UiCanvaPostRT:GetComponent("CanvasScaler")
    if cmp then
        cmp.matchWidthOrHeight = UiManager.screenMatchValue
    end
end

function P:onHide()
    if self._blurRT then
        self._blurRT:Release()
        self._blurRT = nil
    end
end

function P:addNode(node)
    node.transform:SetParent(self.UiCanvaPostRT.transform, false)
end

function P:getRenderTexture()
    return self._blurRT
end

return P