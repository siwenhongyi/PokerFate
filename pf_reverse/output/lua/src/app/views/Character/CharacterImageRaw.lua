local CharacterImageRaw = require("app.views.Character.CharacterImage")
local P = class("CharacterImageRaw", Object)

function P:onAwake()
    for k, v in pairs(CharacterImageRaw) do
        if not self[k] and type(v) == "function" and k ~= "getRoleSpine" then
            self[k] = function(self, ...)
                if self._roleCanvas then
                    self._roleCanvas:invokeSpine(k, ...)

                    if k == "initSpecialInteraction" then
                        local Root = self:find("Root")
                        self:removeAllChildren(Root)
                        local cls = ObjectPool:getCls(self._roleCanvas.CharacterImage)
                        if cls and cls._btnList then
                            for k, v in pairs(cls._btnList) do
                                local n = CU.GameObject.Instantiate(v, Root.transform, false)
                                n.name = k
                                bee.addClick2(n, function()
                                    v:GetComponent("Button").onClick:Invoke()
                                end, true)
                            end
                        end
                    end
                end
            end
        end
    end

    self.RawImage = self:find("RawImage")
end

function P:onDestroy()
    if self._myRoleCanvas then
        self._myRoleCanvas:destroy()
        self._myRoleCanvas = nil
    end
end

function P:getRoleSpine()
    return self:find("Root")
    -- if self._roleCanvas then
    --     return bee.invoke(self._roleCanvas.CharacterImage, "getRoleSpine")
    -- end
    -- return nil
end

function P:setRoleCanvas(ui)
    self._roleCanvas = ui
    local rt = ui:getRenderTexture()
    self.RawImage:GetComponent("RawImage").texture = rt
    self.RawImage.transform.sizeDelta = bee.v2(rt.width, rt.height)
end

function P:createRoleCanvas()
    if not self._myRoleCanvas then
        self._myRoleCanvas = CharacterModel:getRoleCanvas()
        self:setRoleCanvas(self._myRoleCanvas)
    end
end

