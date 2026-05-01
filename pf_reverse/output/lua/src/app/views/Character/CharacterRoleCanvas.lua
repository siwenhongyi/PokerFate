local P = class("CharacterRoleCanvas", UiBase)

function P:onAwake()
    self._isMute = true
    self.RoleCanvas = self:find("RoleCanvas")
    self.RoleCamera = self:find("RoleCamera")

    self.CharacterImage = self:find("CharacterImage/CharacterImage", self.RoleCanvas)
    self.RawImage = self:find("RawImage", self.RoleCanvas)

    self._rt = CU.RenderTexture(SCREEN_WIDTH, SCREEN_HEIGHT, 0)
    self.RoleCamera:GetComponent("Camera").targetTexture = self._rt

    UiManager:_resetScreenMatch(self.RoleCanvas)
end

-- function P:onShow()
--     self._role = self._params and self._params.role or CharacterModel:getUsingRole()
--     self:refreshRole()
-- end

function P:onHide()
    if self._rt then
        self._rt:Release()
        self._rt = nil
    end
end

function P:getRoleImage()
    local roleImage = bee.createObj("views/Character/CharacterImageRaw")
    bee.invoke(roleImage, "setRoleCanvas", self)
    return roleImage
end

function P:getRenderTexture()
    return self._rt
end

function P:refreshRole()
    bee.invoke(self.CharacterImage, "setRole", self._role, true)
end

function P:invokeSpine(...)
    bee.invoke(self.CharacterImage, ...)
end

return P